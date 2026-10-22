<template>
    <v-card variant="flat" class="create-box pa-3 mb-4" data-testid="create-box">
        <div class="d-flex align-center ga-2 mb-1">
            <span class="text-subtitle-2">New {{ info.singular }}</span>
            <span v-if="fromStub" class="text-caption text-muted" data-testid="from-stub">from stub “{{ fromStub.name }}”</span>
            <v-btn v-if="fromStub" icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Not from the stub" :disabled="busy" @click="notFromStub"></v-btn>
            <span v-if="promoting" class="text-caption text-muted" data-testid="promoting">making {{ promoting.kind === 'place' ? 'the place' : '' }} “{{ promoting.name }}” a sphere</span>
            <v-btn v-if="promoting" icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Don't make it a sphere" :disabled="busy" @click="stopPromoting"></v-btn>
        </div>

        <!-- a sphere's template: its starting drawers and agent flag -->
        <div v-if="isSphere" class="d-flex align-center flex-wrap ga-2 mb-2">
            <span class="text-caption text-muted">Template</span>
            <v-btn-toggle v-model="template" density="compact" variant="outlined" divided color="accent" :disabled="busy" data-testid="sphere-template-picker">
                <v-btn v-for="item in templates" :key="item.template" :value="item.template" size="small">{{ item.label }}</v-btn>
            </v-btn-toggle>
            <span v-if="template" class="text-caption text-muted">{{ templateAgent ? 'acts in the world' : 'a body of knowledge' }}</span>
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
            :label="kind === 'mix' || promoting ? 'Describe it (optional)' : 'Describe it'"
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
            <v-select
                v-if="kind === 'place'"
                v-model="parentId"
                label="Inside (place)"
                :items="parentOptions"
                item-title="name"
                item-value="id"
                clearable
                density="compact"
                variant="outlined"
                hide-details
                class="picker picker-wide"
                :disabled="busy"
            ></v-select>
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
                :items="kind === 'event' ? parentOptions : ownerOptions"
                item-title="name"
                item-value="id"
                clearable
                density="compact"
                variant="outlined"
                hide-details
                class="picker picker-wide"
                :disabled="busy"
            ></v-select>
            <v-spacer></v-spacer>
            <v-btn
                color="accent"
                variant="flat"
                size="small"
                prepend-icon="mdi-creation"
                :loading="(isSphere ? worlds.spherePreviewPending : worlds.previewPending) && mine"
                :disabled="!canCreate"
                @click="create"
            >Create</v-btn>
            <v-btn v-if="cancellable || promoting" variant="outlined" size="small" :disabled="!!worlds.pending.accept_preview || !!worlds.pending.accept_sphere" @click="cancel">Cancel</v-btn>
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

        <SpherePreviewCard
            v-if="spherePreview"
            :preview="spherePreview"
            class="mt-3"
            @accept="worlds.acceptSphere({ name: $event })"
            @regenerate="worlds.regenerateSpherePreview()"
            @discard="worlds.discardSpherePreview()"
        />

        <v-card v-if="preview" variant="tonal" class="preview mt-3 pa-3" data-testid="create-preview">
            <div class="d-flex align-center ga-2 mb-2">
                <v-text-field
                    v-model="previewName"
                    label="Name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="preview-name"
                ></v-text-field>
                <span v-if="preview.fields.born" class="text-caption text-muted">
                    born <span class="world-date">{{ formatDate(worlds.calendar, preview.fields.born) }}</span>
                </span>
            </div>

            <!-- named like a stub of this kind: the owner may fill that
                 stub rather than make a second one -->
            <v-alert v-if="matchingStub" type="info" variant="tonal" density="compact" class="mb-2" data-testid="matching-stub">
                <div class="d-flex align-center flex-wrap ga-2">
                    <span>There is a stub named “{{ matchingStub.name }}” already.</span>
                    <v-spacer></v-spacer>
                    <v-btn
                        color="accent"
                        variant="flat"
                        size="small"
                        :loading="!!worlds.pending.accept_preview"
                        :disabled="!previewName.trim()"
                        @click="accept(matchingStub.id)"
                    >Fill the stub “{{ matchingStub.name }}” instead</v-btn>
                </div>
            </v-alert>

            <div v-for="(text, section) in preview.prose" :key="section" class="mb-2">
                <div class="text-caption text-muted text-uppercase">{{ section }}</div>
                <div class="prose">{{ text }}</div>
            </div>

            <div class="text-caption text-muted text-uppercase mt-2">Facts</div>
            <div v-for="(fact, index) in preview.facts" :key="index" class="fact d-flex align-center ga-2">
                <span class="flex-grow-1"><LinkedText :segments="previewSegments(fact.text, preview.new_names)" :text="fact.text" /></span>
                <v-chip size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
                <span class="fact-date">{{ fact.since ? formatDate(worlds.calendar, fact.since) + ' →' : 'always' }}</span>
            </div>

            <!-- the sphere drawer an expanded stub joins -->
            <div v-if="preview.part_of" class="text-body-2 mt-2" data-testid="preview-part-of">
                <span class="text-muted">Part of</span> {{ partOfName }} <span class="text-muted">— {{ partOfDrawer }}</span>
            </div>

            <!-- a character's proposed ties: each, and each "but…", can be
                 dropped before accepting -->
            <template v-if="preview.ties && preview.ties.length">
                <div class="text-caption text-muted text-uppercase mt-3">Ties</div>
                <div v-for="(tie, tieIndex) in preview.ties" :key="tie.sphere_id + tieIndex" class="preview-tie" data-testid="preview-tie">
                    <div class="d-flex align-center ga-1">
                        <span class="flex-grow-1">{{ tieLead(tie.role) }} <span class="tie-sphere">{{ tie.sphere }}</span><span v-if="tie.since" class="text-muted"> · since {{ formatDate(worlds.calendar, tie.since) }}</span></span>
                        <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Drop tie" @click="worlds.dropPreviewTie(tieIndex)"></v-btn>
                    </div>
                    <template v-if="tie.exceptions.length">
                        <div class="but"><i>but…</i></div>
                        <div v-for="(exception, index) in tie.exceptions" :key="index" class="but d-flex align-center ga-1" data-testid="preview-tie-exception">
                            <span class="flex-grow-1">– {{ exception.text }} <span class="text-muted">(departs from {{ exception.item }})</span></span>
                            <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Drop exception" @click="worlds.dropPreviewException(tieIndex, index)"></v-btn>
                        </div>
                    </template>
                    <div v-else class="but text-muted">no exceptions</div>
                </div>
            </template>

            <!-- what it inherits, each ticked as kept: unticking one the
                 model missed marks it replaced by one of the preview's own -->
            <template v-if="preview.inherited && preview.inherited.length">
                <div class="text-caption text-muted text-uppercase mt-3">Inherited (untick to replace)</div>
                <div
                    v-for="row in preview.inherited"
                    :key="row.fact_id"
                    class="fact inherited d-flex align-center ga-2"
                    data-testid="preview-inherited"
                >
                    <v-checkbox-btn
                        :model-value="overriderOf(row) < 0"
                        aria-label="Kept"
                        density="compact"
                        class="flex-grow-0"
                        :disabled="!preview.facts.length"
                        @update:model-value="setKept(row, $event)"
                    ></v-checkbox-btn>
                    <span class="flex-grow-1" :class="{ replaced: overriderOf(row) >= 0 }">{{ row.text }}</span>
                    <v-select
                        v-if="overriderOf(row) >= 0"
                        :model-value="overriderOf(row)"
                        :items="ownFactItems"
                        label="Replaced by"
                        density="compact"
                        variant="outlined"
                        hide-details
                        class="override-by"
                        data-testid="override-by"
                        @update:model-value="worlds.setPreviewOverride(row.fact_id, $event)"
                    ></v-select>
                    <v-chip size="x-small" label variant="tonal" color="muted">{{ row.source }}</v-chip>
                </div>
            </template>

            <div class="d-flex ga-2 mt-3">
                <v-btn
                    color="accent"
                    variant="flat"
                    size="small"
                    prepend-icon="mdi-check"
                    :loading="!!worlds.pending.accept_preview"
                    :disabled="!previewName.trim()"
                    @click="accept()"
                >Accept</v-btn>
                <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" :disabled="!!worlds.pending.accept_preview" @click="worlds.regeneratePreview()">Regenerate</v-btn>
                <v-btn variant="outlined" size="small" prepend-icon="mdi-pencil" :disabled="!!worlds.pending.accept_preview" @click="worlds.discardPreview()">Edit</v-btn>
            </div>
        </v-card>
    </v-card>
</template>

<script>
import { defaultOverrideIndex, heritageFromMatches, previewSegments, sameParents, useWorldsStore } from '@/stores/worlds.js';
import { dateOf, formatDate } from './worldDates.js';
import { SPHERE_TEMPLATES, UNSORTED, kindInfo, templateInfo, tieLead } from './worldKinds.js';
import { NEW_THING, linkPayload, pickedId, repicks } from './nameHighlights.js';
import HeritagePicker from './HeritagePicker.vue';
import LinkedText from './LinkedText.vue';
import NameHighlightInput from './NameHighlightInput.vue';
import SpherePreviewCard from './SpherePreviewCard.vue';

const PLACEHOLDERS = {
    character: 'A grizzled ferryman who owes the Wardens more than money…',
    place: 'A half-flooded market town on the river, a little shady…',
    lore: 'The old treaty that sets the river tolls…',
    species: 'Owl-folk: small feathered people with wings instead of arms…',
    race: 'The largest of them, white-plumaged, from the frozen north…',
    mix: 'Anything the blend should settle; the parents are enough to start from…',
    event: 'The night the river froze solid and the ferries stopped…',
    sphere: 'The state church of the north, which teaches the change was a purification…',
    item: 'A tarnished ferryman’s bell said to wake the drowned…',
};

// a year field as a wire date, or null when unset or out of range
function yearDate(year) {
    return Number.isInteger(year) && year >= 1 && year <= 9999 ? dateOf(year) : null;
}

// The "describe it, then create" box for one kind: a prompt plus the
// optional core-field pickers (born for characters, the parent place for
// places, the heritage picker for characters and mixes). Create shows the
// backend's preview, which can be accepted, regenerated, or dropped to edit
// the prompt and try again.
//
// The prompt is a `NameHighlightInput`: its names highlight as you type,
// each open to a re-pick or "treat as new", and right-click adds a
// reference. The preview is asked for with those picks; a re-pick teaches
// its thing the name as written once the preview is accepted. "Context the
// AI gets" shows the stub's mentions and the names the prompt names. A
// preview of a new thing named like a stub of its kind offers to fill that
// stub instead (`into_stub`).
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
// meanwhile, and the preview carries the stub's id, so accepting fills the
// stub in place. An event's picks
// are its years and place, an item's its owner.
//
// The Spheres box (kind "sphere") picks a template (a sphere stub's guess
// to start with) and previews the sphere's core (`preview_sphere`,
// `SpherePreviewCard`: summary, timeline, drawer outline, the entries it
// adopts): a new sphere, a stub it expands (any stub "Make it a sphere…"
// was used on), or the lore entry or place it promotes (`promoting`,
// whose prompt is optional). A character preview shows its proposed ties,
// each tie and each "but…" droppable before accepting, and an expanded
// stub's preview the sphere it joins (`part_of`).
export default {
    name: 'CreateBox',
    components: { HeritagePicker, LinkedText, NameHighlightInput, SpherePreviewCard },
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
            parentId: null,
            previewName: '',
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
            // a sphere's template
            template: null,
            templates: SPHERE_TEMPLATES,
        };
    },
    computed: {
        info() {
            return kindInfo(this.kind);
        },
        placeholder() {
            return PLACEHOLDERS[this.kind] || '';
        },
        parentOptions() {
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
        isSphere() {
            return this.kind === 'sphere';
        },
        // the thing "Make it a sphere…" promotes (the Spheres box only)
        promoting() {
            return this.isSphere ? this.worlds.promoting : null;
        },
        templateAgent() {
            return templateInfo(this.template).agent;
        },
        // the store's preview request is this box's
        mine() {
            if (this.isSphere) {
                return !!this.worlds.spherePreviewRequest;
            }
            return this.worlds.previewRequest?.kind === this.kind;
        },
        preview() {
            return this.mine && !this.isSphere ? this.worlds.preview : null;
        },
        spherePreview() {
            return this.mine && this.isSphere ? this.worlds.spherePreview : null;
        },
        previewError() {
            return this.isSphere ? this.worlds.spherePreviewError : this.worlds.previewError;
        },
        busy() {
            if (this.isSphere) {
                return (this.mine && this.worlds.spherePreviewPending) || !!this.worlds.pending.accept_sphere;
            }
            return (this.mine && this.worlds.previewPending) || !!this.worlds.pending.accept_preview || this.lookingUp;
        },
        // the sphere a preview's expanded stub joins, and its drawer
        partOfName() {
            const id = this.preview?.part_of?.sphere;
            return this.worlds.referenceTargets.find((target) => target.id === id)?.name || 'a sphere';
        },
        partOfDrawer() {
            const link = this.preview?.part_of;
            if (!link || link.drawer === UNSORTED) {
                return 'Unsorted';
            }
            const drawers = this.worlds.sphereInfo[link.sphere]?.sphere?.drawers || [];
            return drawers.find((drawer) => drawer.id === link.drawer)?.title || 'a drawer';
        },
        lookingUp() {
            return !!this.awaitingMix && !!this.worlds.mixLookup;
        },
        hint() {
            if (this.isSphere) {
                return 'Pick a template; the AI writes its summary, timeline and drawer outline, then Fill writes a drawer.';
            }
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
            if (this.isSphere) {
                return !!this.template && (!!this.prompt.trim() || !!this.promoting || !!this.fromStub);
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
            const preview = this.preview || this.spherePreview;
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
        // the stub of this kind the preview is named like (not one it expands)
        matchingStub() {
            const id = this.preview?.matching_stub_id;
            if (!id || this.preview.stub_id) {
                return null;
            }
            return { id, name: this.worlds.stubInfo(id)?.name || this.preview.name };
        },
        // the draft's notice: why it's there, and that the character waits
        mixDraftNotice() {
            const names = this.parents.map((id) => this.heritageName(id) || 'this parent');
            return `${names.join(' and ')} have no mix yet. Every character of two parents shares one mix, so draft it here first; once you accept it, this character carries on with it as heritage.`;
        },
        ownFactItems() {
            return (this.preview?.facts || []).map((fact, index) => ({ title: fact.text, value: index }));
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
                    // a sphere stub's guessed template
                    if (this.isSphere) {
                        const listed = (this.worlds.things.sphere || []).find((thing) => thing.id === stub.id);
                        this.template = listed?.template || this.template;
                    }
                }
            },
            immediate: true,
        },
        // promoting starts from its name: the prompt is optional
        promoting: {
            handler(thing, before) {
                if (thing && thing.id !== before?.id) {
                    this.prompt = '';
                    this.template = null;
                }
            },
            immediate: true,
        },
        // a character preview joining a sphere names its drawer
        'preview.part_of'(link) {
            if (link && link.drawer !== UNSORTED) {
                this.worlds.fetchSphere(link.sphere);
            }
        },
        // the sphere request is gone once accepted: start afresh
        'worlds.spherePreviewRequest'(request, before) {
            if (this.isSphere && !request && before) {
                this.prompt = this.suggestion?.prompt || this.fromStub?.name || '';
                this.picks = {};
                this.refs = {};
                this.template = null;
            }
        },
        // the suggested prompt replaces the stub's bare name, unless the
        // owner has written something else meanwhile
        suggestion(found) {
            if (found && (!this.prompt.trim() || this.prompt === this.fromStub?.name)) {
                this.prompt = found.prompt;
            }
        },
        // immediate: the box is keyed by kind, so it remounts (switching
        // kinds and back) with a preview already there
        preview: {
            handler(preview) {
                this.previewName = preview?.name || '';
            },
            immediate: true,
        },
        // the request is gone once its preview is accepted (or the world
        // changes): start the box afresh
        'worlds.previewRequest'(request, before) {
            if (!request && before?.kind === this.kind) {
                // expanding a stub drops the box's old preview: it starts
                // from the stub
                this.prompt = this.suggestion?.prompt || this.fromStub?.name || '';
                this.picks = {};
                this.refs = {};
                this.bornYear = null;
                this.parentId = null;
                this.eventYears = { when: null, until: null };
                this.linkedId = null;
                this.parents = [...(this.preset.parents || [])];
                this.pickTouched = false;
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
        'worlds.accepted'(accepted) {
            if (accepted && this.accepting) {
                this.accepting = false;
                this.$emit('accepted', accepted);
            }
        },
    },
    methods: {
        formatDate,
        previewSegments,
        tieLead,
        // the box goes on as a plain one: a preview made from the stub goes
        notFromStub() {
            if (this.mine) {
                this.dropPreview();
            }
            this.worlds.stopExpanding();
        },
        stopPromoting() {
            if (this.mine) {
                this.dropPreview();
            }
            this.worlds.stopPromoting();
        },
        dropPreview() {
            if (this.isSphere) {
                this.worlds.cancelSpherePreview();
            } else {
                this.worlds.cancelPreview();
            }
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
            if (this.kind === 'place' && this.parentId) {
                fields.parent = this.parentId;
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
            if (this.isSphere) {
                this.requestSpherePreview();
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
        // a sphere's core: from the stub it expands, or for the thing it
        // promotes
        requestSpherePreview() {
            const links = linkPayload(this.matches, this.picks, this.refs, this.prompt);
            const own = this.fromStub?.id || this.promoting?.id;
            links.picks = Object.fromEntries(Object.entries(links.picks).filter(([, id]) => id !== own));
            this.worlds.previewSphere(this.template, this.prompt.trim(), {}, {
                stubId: this.fromStub?.id || null,
                promoteId: this.promoting?.id || null,
                picks: links.picks,
                newNames: links.newNames,
            });
        },
        // `intoStub`: fill that stub instead of making a new thing
        accept(intoStub = null) {
            this.accepting = this.stay;
            this.worlds.acceptPreview({ name: this.previewName.trim() }, { open: !this.stay, intoStub });
        },
        cancel() {
            if (this.mine) {
                this.dropPreview();
            }
            if (this.fromStub) {
                this.worlds.stopExpanding();
            }
            if (this.promoting) {
                this.worlds.stopPromoting();
            }
            this.$emit('cancel');
        },
        // the mix drafted first is the character's heritage now
        mixAccepted(mix) {
            this.mixDraft = false;
            this.parents = [mix.id];
            this.pickTouched = true;
        },
        // the own fact replacing the inherited `row`, or -1
        overriderOf(row) {
            return this.preview.facts.findIndex((fact) => (fact.overrides || []).includes(row.fact_id));
        },
        // ticked: inherited as it is; unticked: replaced by an own fact
        setKept(row, kept) {
            this.worlds.setPreviewOverride(row.fact_id, kept ? null : defaultOverrideIndex(this.preview, row));
        },
    },
};
</script>

<style scoped>
.create-box {
    background: rgb(var(--v-theme-raised));
}

.picker {
    max-width: 160px;
}

.picker-wide {
    max-width: 260px;
}

.override-by {
    flex: none;
    width: 220px;
}

.replaced {
    text-decoration: line-through;
    color: rgb(var(--v-theme-muted));
}

.inherited {
    color: rgb(var(--v-theme-muted));
}

.mix-draft {
    border-left: 2px solid rgb(var(--v-theme-accent));
    padding-left: 10px;
}

.mix-link {
    color: rgb(var(--v-theme-accent));
}

.preview-name {
    max-width: 320px;
}

.prose {
    line-height: 1.5;
    white-space: pre-wrap;
}

.fact {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 4px 0;
}

.fact .v-chip {
    flex: none;
}

.fact-date {
    flex: none;
    font-family: monospace;
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
    min-width: 70px;
    text-align: right;
}

.world-date {
    color: rgb(var(--v-theme-date));
}

.preview-tie {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    padding: 6px 10px;
    margin: 6px 0;
}

.preview-tie .v-btn {
    flex: none;
}

.tie-sphere {
    color: rgb(var(--v-theme-link));
}

.but {
    margin: 2px 0 0 14px;
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
