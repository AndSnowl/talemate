<template>
    <v-card variant="flat" class="create-box pa-3 mb-4" :class="{ drafting: showingDraft }" data-testid="create-box">
        <!-- the draft is the page the entry will be: it stands in for the
             form until it's accepted, discarded or its prompt edited -->
        <ThingPage v-if="showingDraft" draft :stay="stay" />
        <div v-show="!showingDraft">
        <div class="d-flex align-center ga-2 mb-1">
            <span class="text-subtitle-2">New {{ info.singular }}</span>
            <span v-if="fromStub" class="text-caption text-muted" data-testid="from-stub">from stub “{{ fromStub.name }}”</span>
            <v-chip v-if="fromStub" size="x-small" label variant="outlined" color="foreign" class="stub-tag" :class="{ untagged: !fromStubTag }" data-testid="from-stub-tag" :title="fromStubTag ? 'The stub\'s tag: the draft keeps it' : 'No tag yet: the AI is asked for one'">{{ fromStubTag || 'no tag' }}</v-chip>
            <v-btn v-if="fromStub" icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Not from the stub" :disabled="busy" @click="notFromStub"></v-btn>
        </div>

        <div v-if="speciesName" class="text-caption text-muted mb-2">Race of {{ speciesName }}</div>
        <HeritagePicker
            v-if="hasPicker"
            v-model="parents"
            :kind="kind"
            :disabled="busy || lockParents || mixDraft"
            class="mb-2"
            @update:model-value="pickTouched = true"
        />
        <NameHighlightInput
            v-model="prompt"
            v-model:picks="picks"
            v-model:refs="refs"
            :context-thing-id="null"
            :context-kind="kind"
            :label="kind === 'mix' ? 'Describe it (optional)' : 'Describe it'"
            :placeholder="placeholder"
            :rows="2"
            :debounce="400"
            :disabled="busy"
        />

        <div class="d-flex align-center flex-wrap ga-2 mt-2">
            <v-text-field
                v-if="kind === 'character'"
                v-model.number="bornYear"
                label="Born (year)"
                type="number"
                min="1"
                max="9999"
                density="compact"
                variant="outlined"
                hide-details
                class="picker"
                :disabled="busy"
            ></v-text-field>
            <template v-if="kind === 'event'">
                <v-text-field
                    v-for="field in ['when', 'until']"
                    :key="field"
                    v-model.number="eventYears[field]"
                    :label="field === 'when' ? 'When (year)' : 'Until (year)'"
                    type="number"
                    min="1"
                    max="9999"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="picker"
                    :disabled="busy"
                ></v-text-field>
            </template>
            <v-select
                v-if="kind === 'event' || kind === 'item'"
                v-model="linkedId"
                :label="kind === 'event' ? 'Place' : 'Owner (character)'"
                :items="kind === 'event' ? placeOptions : ownerOptions"
                item-title="name"
                item-value="id"
                clearable
                density="compact"
                variant="outlined"
                hide-details
                class="picker picker-wide"
                :disabled="busy"
            ></v-select>
            <v-btn
                color="accent"
                variant="flat"
                size="small"
                prepend-icon="mdi-creation"
                :loading="worlds.previewPending && mine"
                :disabled="!canCreate"
                @click="create"
            >Create</v-btn>
            <v-btn v-if="cancellable" variant="outlined" size="small" :disabled="!!worlds.pending.accept_preview" @click="cancel">Cancel</v-btn>
        </div>
        <div class="text-caption text-muted mt-1">{{ hint }}</div>

        <!-- what the AI is given besides the prompt: the stub's mentions
             (and the key facts of what mentions it), the things the
             prompt names -->
        <v-expansion-panels v-if="contextGroups.length || namedInPrompt.length" variant="accordion" class="ai-context mt-2" data-testid="ai-context">
            <v-expansion-panel elevation="0">
                <v-expansion-panel-title class="text-caption">Context the AI gets</v-expansion-panel-title>
                <v-expansion-panel-text>
                    <div v-if="contextGroups.length" class="text-caption text-muted text-uppercase">{{ fromStub ? 'Mentioned in' : 'Context' }}</div>
                    <div v-for="([heading, facts], index) in contextGroups" :key="index" class="context-group mb-2" data-testid="context-group">
                        <div class="context-heading">{{ heading }}</div>
                        <div v-for="(fact, factIndex) in facts" :key="factIndex" class="context-fact">{{ fact }}</div>
                    </div>
                    <div v-if="namedInPrompt.length" class="mt-1" data-testid="context-named">
                        <span class="text-caption text-muted text-uppercase">Named in this prompt</span>
                        <div class="d-flex flex-wrap ga-1 mt-1">
                            <v-chip v-for="named in namedInPrompt" :key="named.id" size="small" label variant="tonal" :color="named.stub ? 'foreign' : 'link'">
                                {{ named.name }}<span class="text-muted ml-1">({{ named.stub ? 'stub' : 'existing' }})</span>
                            </v-chip>
                        </div>
                        <div class="text-caption text-muted mt-1">Their facts come along.</div>
                    </div>
                </v-expansion-panel-text>
            </v-expansion-panel>
        </v-expansion-panels>

        <!-- two parents with no mix yet: the mix is drafted here, under
             the character (whose prompt stays as it is), then the box
             carries on with it as the character's heritage -->
        <div v-if="mixDraft" class="mix-draft mt-3" data-testid="mix-draft">
            <v-alert type="info" variant="tonal" density="compact" class="mb-2">{{ mixDraftNotice }}</v-alert>
            <CreateBox kind="mix" :preset="{ parents }" lock-parents stay cancellable @accepted="mixAccepted" @cancel="mixDraft = false" />
        </div>

        <v-alert v-if="existingMix" type="info" variant="tonal" density="compact" class="mt-3" data-testid="mix-exists">
            These parents already have a mix:
            <a href="#" class="mix-link" @click.prevent="worlds.openThing(existingMix.id)">{{ existingMix.name }}</a>.
        </v-alert>

        <v-alert v-if="mine && previewError" type="error" variant="tonal" density="compact" class="mt-3">
            {{ previewError }}
        </v-alert>
        </div>
    </v-card>
</template>

<script>
import { defineAsyncComponent } from 'vue';
import { heritageFromMatches, sameParents, useWorldsStore } from '@/stores/worlds.js';
import { dateOf } from './worldDates.js';
import { kindInfo } from './worldKinds.js';
import { NEW_THING, linkPayload, pickedId, repicks } from './nameHighlights.js';
import HeritagePicker from './HeritagePicker.vue';
import NameHighlightInput from './NameHighlightInput.vue';

const PLACEHOLDERS = {
    character: 'A grizzled ferryman who owes the Wardens more than money…',
    place: 'A half-flooded market town on the river, a little shady…',
    lore: 'The old treaty that sets the river tolls…',
    species: 'Owl-folk: small feathered people with wings instead of arms…',
    race: 'The largest of them, white-plumaged, from the frozen north…',
    mix: 'Anything the blend should settle; the parents are enough to start from…',
    event: 'The night the river froze solid and the ferries stopped…',
    item: 'A tarnished ferryman’s bell said to wake the drowned…',
    being: 'The river spirit the ferrymen leave bread for…',
};

// a year field as a wire date, or null when unset or out of range
function yearDate(year) {
    return Number.isInteger(year) && year >= 1 && year <= 9999 ? dateOf(year) : null;
}

// The "describe it, then create" box for one kind: a prompt plus the
// optional core-field pickers (born for characters, the heritage picker for
// characters and mixes). Create opens the draft: the page the entry will
// be (the entry page's draft mode, `ThingPage draft`, standing in for the
// form), with its bar (`DraftBar`) holding the prompt, to regenerate,
// discard or accept it. Nothing is written before Accept. While the draft
// is open, this box's own form is hidden: only one prompt box shows for a
// given draft. Discard brings the form back, the (possibly edited) prompt
// kept as the owner left it in the bar.
//
// The box's own prompt, before a draft exists, is a `NameHighlightInput`:
// its names highlight as you type,
// each open to a re-pick or "treat as new", and right-click adds a
// reference. The draft is asked for with those picks; a re-pick teaches
// its thing the name as written once the draft is accepted. "Context the
// AI gets" shows the stub's mentions and the names the prompt names.
//
// Heritage: a character's picker is pre-filled from the heritage its
// prompt names, until the owner picks one. Two parents always go through a
// mix: Create asks `find_mix` first; an existing mix becomes the heritage,
// and with none the box drafts the mix in place (a nested mix box, `stay`,
// under the character's own form, which stays on screen untouched) and
// comes back with it picked. A mix box refuses parents
// that already have a mix. `preset` fixes a race's `species` or a mix's
// first parent (the species page's "+ New race" and "+ New mix").
//
// Expanding a stub (`worlds.expanding`, of this box's kind) starts the box
// from it: the prompt starts as the stub's name, then as the suggestion
// made from its mentions (`stub_suggestion`) unless the owner has typed
// meanwhile, and the draft carries the stub's id, so accepting fills the
// stub in place. The header shows the stub's tag ("no tag" dimmed: the
// AI is asked for one). An event's picks
// are its years and place, an item's its owner. A nested box (`stay`, the
// mix drafted for a character) shows its draft in place too, and accepting
// it doesn't open its page.
export default {
    name: 'CreateBox',
    components: {
        // the entry page, in its draft mode; async, since a species' page
        // holds this box (its "+ New race" and "+ New mix")
        ThingPage: defineAsyncComponent(() => import('./ThingPage.vue')),
        HeritagePicker,
        NameHighlightInput,
    },
    props: {
        kind: { type: String, required: true },
        // `{species}` for a race, `{parents}` for a mix
        preset: { type: Object, default: () => ({}) },
        lockParents: { type: Boolean, default: false },
        // accepting doesn't open the new thing's page: it's emitted instead
        stay: { type: Boolean, default: false },
        cancellable: { type: Boolean, default: false },
    },
    emits: ['accepted', 'cancel'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            prompt: '',
            // the prompt's names: pickKey -> thing id or NEW_THING, and the
            // references added by hand (pickKey -> {id, text})
            picks: {},
            refs: {},
            bornYear: null,
            parents: [...(this.preset.parents || [])],
            // the owner picked a heritage: the prompt no longer pre-fills it
            pickTouched: false,
            // the parents a `find_mix` is out for
            awaitingMix: null,
            // the mix these parents already have (a mix box)
            existingMix: null,
            mixDraft: false,
            accepting: false,
            // an event's `when`/`until` years
            eventYears: { when: null, until: null },
            // an event's place, or an item's owner
            linkedId: null,
        };
    },
    computed: {
        info() {
            return kindInfo(this.kind);
        },
        placeholder() {
            return PLACEHOLDERS[this.kind] || '';
        },
        placeOptions() {
            return this.worlds.things.place || [];
        },
        ownerOptions() {
            return this.worlds.things.character || [];
        },
        // the stub this box expands
        fromStub() {
            const stub = this.worlds.expanding;
            return stub && stub.kind === this.kind ? stub : null;
        },
        // the expanded stub's tag, as the stubs list has it (the draft
        // keeps it; with none, the AI is asked for one)
        fromStubTag() {
            return this.fromStub ? (this.fromStub.tag ?? this.worlds.stubInfo(this.fromStub.id)?.tag ?? null) : null;
        },
        // the store's preview request is this box's
        mine() {
            return this.worlds.previewRequest?.kind === this.kind;
        },
        // the box's draft (its kind's), and whether it stands in for the form
        draft() {
            return this.mine ? this.worlds.draft : null;
        },
        showingDraft() {
            return !!this.draft;
        },
        previewError() {
            return this.worlds.previewError;
        },
        busy() {
            return (this.mine && this.worlds.previewPending) || !!this.draft?.accepting || this.lookingUp;
        },
        lookingUp() {
            return !!this.awaitingMix && !!this.worlds.mixLookup;
        },
        hint() {
            return this.kind === 'mix'
                ? 'Pick both parents; the AI drafts the blend, and a description is optional.'
                : 'Pickers are optional; the AI fills in the rest from your description.';
        },
        // a character's picker shows once the world has a heritage to pick
        hasPicker() {
            return this.kind === 'mix' || (this.kind === 'character' && (this.worlds.heritage.length > 0 || this.parents.length > 0));
        },
        speciesName() {
            return this.kind === 'race' ? this.heritageName(this.preset.species) : '';
        },
        canCreate() {
            if (this.busy || this.mixDraft || !this.validYears) {
                return false;
            }
            if (this.kind === 'mix') {
                return this.parents.length === 2;
            }
            return !!this.prompt.trim();
        },
        // the prompt's name matches, once looked up
        matches() {
            return this.worlds.matchesFor(this.prompt, null);
        },
        // the expanded stub's suggestion, once it's come
        suggestion() {
            const found = this.worlds.stubSuggestion;
            return this.fromStub && found?.id === this.fromStub.id ? found : null;
        },
        // `[heading, facts]` groups: the preview's own once there is one,
        // else the stub's mention context
        contextGroups() {
            const preview = this.draft?.edited;
            if (preview) {
                return preview.context || [];
            }
            return this.suggestion?.context || [];
        },
        // the world things the prompt names (as picked), once each; not the
        // stub being expanded, which its suggested prompt names
        namedInPrompt() {
            const named = new Map();
            for (const match of this.matches) {
                const id = pickedId(match, this.picks, this.refs);
                const candidate = match.candidates.find((c) => c.id === id);
                if (id !== NEW_THING && id !== this.fromStub?.id && !named.has(id)) {
                    const target = candidate || this.worlds.referenceTargets.find((t) => t.id === id);
                    named.set(id, { id, name: target?.name || match.text, stub: !!target?.stub });
                }
            }
            return [...named.values()];
        },
        // the draft's notice: why it's there, and that the character waits
        mixDraftNotice() {
            const names = this.parents.map((id) => this.heritageName(id) || 'this parent');
            return `${names.join(' and ')} have no mix yet. Every character of two parents shares one mix, so draft it here first; once you accept it, this character carries on with it as heritage.`;
        },
        validYears() {
            const valid = (year) => year === null || year === '' || (Number.isInteger(year) && year >= 1 && year <= 9999);
            return valid(this.bornYear) && valid(this.eventYears.when) && valid(this.eventYears.until);
        },
    },
    watch: {
        fromStub: {
            handler(stub, before) {
                if (stub && stub.id !== before?.id) {
                    this.prompt = this.suggestion?.prompt || stub.name;
                }
            },
            immediate: true,
        },
        // the suggested prompt replaces the stub's bare name, unless the
        // owner has written something else meanwhile
        suggestion(found) {
            if (found && (!this.prompt.trim() || this.prompt === this.fromStub?.name)) {
                this.prompt = found.prompt;
            }
        },
        // the request is gone once its draft is accepted (or the world
        // changes): start the box afresh
        'worlds.previewRequest'(request, before) {
            if (!request && before?.kind === this.kind) {
                // expanding a stub drops the box's old preview: it starts
                // from the stub
                this.prompt = this.suggestion?.prompt || this.fromStub?.name || '';
                this.picks = {};
                this.refs = {};
                this.bornYear = null;
                this.eventYears = { when: null, until: null };
                this.linkedId = null;
                this.parents = [...(this.preset.parents || [])];
                this.pickTouched = false;
            }
        },
        // Discard: the draft goes but the request (and its prompt, as the
        // owner left it in the bar) stays, so the form comes back with it
        draft(now, before) {
            if (!now && before && this.mine) {
                this.prompt = this.worlds.previewRequest?.prompt ?? this.prompt;
            }
        },
        matches(matches) {
            if (this.kind === 'character' && !this.pickTouched) {
                const id = heritageFromMatches(matches, this.worlds.heritage);
                this.parents = id ? [id] : [];
            }
        },
        parents() {
            this.existingMix = null;
        },
        'worlds.mixFound'(found) {
            if (!found || !this.awaitingMix || !sameParents(found.parents, this.awaitingMix)) {
                return;
            }
            this.awaitingMix = null;
            if (this.kind === 'mix') {
                if (found.mix_id) {
                    this.existingMix = { id: found.mix_id, name: this.heritageName(found.mix_id) };
                } else {
                    this.requestPreview();
                }
            } else if (found.mix_id) {
                this.parents = [found.mix_id];
                this.requestPreview();
            } else {
                this.mixDraft = true;
            }
        },
        // a nested box's draft is being accepted: its `accepted` is ours
        'worlds.draft.accepting'(now) {
            if (now && this.mine) {
                this.accepting = this.stay;
            }
        },
        'worlds.accepted'(accepted) {
            if (accepted && this.accepting) {
                this.accepting = false;
                this.$emit('accepted', accepted);
            }
        },
    },
    methods: {
        // the box goes on as a plain one: a draft made from the stub goes
        notFromStub() {
            if (this.mine) {
                this.dropPreview();
            }
            this.worlds.stopExpanding();
        },
        dropPreview() {
            this.worlds.cancelPreview();
        },
        heritageName(id) {
            return this.worlds.heritage.find((item) => item.id === id)?.name || '';
        },
        fields() {
            const fields = {};
            if (this.kind === 'character' && Number.isInteger(this.bornYear)) {
                fields.born = dateOf(this.bornYear);
            }
            if (this.kind === 'character' && this.parents.length === 1) {
                fields.heritage = this.parents[0];
            }
            if (this.kind === 'race' && this.preset.species) {
                fields.species = this.preset.species;
            }
            if (this.kind === 'mix') {
                fields.parents = [...this.parents];
            }
            if (this.kind === 'event') {
                for (const field of ['when', 'until']) {
                    const date = yearDate(this.eventYears[field]);
                    if (date) {
                        fields[field] = date;
                    }
                }
            }
            if ((this.kind === 'event' || this.kind === 'item') && this.linkedId) {
                fields[this.kind === 'event' ? 'place' : 'owner'] = this.linkedId;
            }
            return fields;
        },
        // two parents look for their mix first (see the component comment)
        create() {
            if (!this.canCreate) {
                return;
            }
            this.existingMix = null;
            if (this.parents.length === 2) {
                this.awaitingMix = [...this.parents];
                this.worlds.findMix(this.awaitingMix);
                return;
            }
            this.requestPreview();
        },
        requestPreview() {
            const links = linkPayload(this.matches, this.picks, this.refs, this.prompt);
            // the stub being expanded isn't context for itself, and learns
            // no other name from its own prompt
            const stubId = this.fromStub?.id;
            links.picks = Object.fromEntries(Object.entries(links.picks).filter(([, id]) => id !== stubId));
            this.worlds.previewThing(this.kind, this.prompt.trim(), this.fields(), stubId || null, {
                picks: links.picks,
                newNames: links.newNames,
                repicks: repicks(this.matches, this.picks).filter((repick) => repick.id !== stubId),
            });
        },
        cancel() {
            if (this.mine) {
                this.dropPreview();
            }
            if (this.fromStub) {
                this.worlds.stopExpanding();
            }
            this.$emit('cancel');
        },
        // the mix drafted first is the character's heritage now
        mixAccepted(mix) {
            this.mixDraft = false;
            this.parents = [mix.id];
            this.pickTouched = true;
        },
    },
};
</script>

<style scoped>
.stub-tag.untagged {
    opacity: 0.6;
}

.create-box {
    background: rgb(var(--v-theme-raised));
}

.create-box.drafting {
    background: transparent;
    padding: 0 !important;
}

.picker {
    max-width: 160px;
}

.picker-wide {
    max-width: 260px;
}

.mix-draft {
    border-left: 2px solid rgb(var(--v-theme-accent));
    padding-left: 10px;
}

.mix-link {
    color: rgb(var(--v-theme-accent));
}

.ai-context :deep(.v-expansion-panel) {
    background: transparent;
    border: 1px solid rgb(var(--v-theme-border));
}

.ai-context :deep(.v-expansion-panel-title) {
    min-height: 32px;
    padding: 4px 12px;
}

.context-group {
    border-left: 2px solid rgb(var(--v-theme-border));
    padding-left: 8px;
}

.context-heading {
    font-weight: 600;
    font-size: 13px;
}

.context-fact {
    font-size: 13px;
    line-height: 1.5;
    color: rgb(var(--v-theme-muted));
}
</style>
