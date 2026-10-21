<template>
    <v-card variant="flat" class="create-box pa-3 mb-4" data-testid="create-box">
        <div class="text-subtitle-2 mb-1">New {{ info.singular }}</div>

        <div v-if="speciesName" class="text-caption text-muted mb-2">Race of {{ speciesName }}</div>
        <HeritagePicker
            v-if="hasPicker"
            v-model="parents"
            :kind="kind"
            :disabled="busy || lockParents || mixDraft"
            class="mb-2"
            @update:model-value="pickTouched = true"
        />
        <v-textarea
            v-model="prompt"
            :label="kind === 'mix' ? 'Describe it (optional)' : 'Describe it'"
            :placeholder="placeholder"
            rows="2"
            auto-grow
            density="compact"
            variant="outlined"
            hide-details
            :disabled="busy"
        ></v-textarea>

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
            <v-spacer></v-spacer>
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

        <v-alert v-if="mine && worlds.previewError" type="error" variant="tonal" density="compact" class="mt-3">
            {{ worlds.previewError }}
        </v-alert>

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

            <div v-for="(text, section) in preview.prose" :key="section" class="mb-2">
                <div class="text-caption text-muted text-uppercase">{{ section }}</div>
                <div class="prose">{{ text }}</div>
            </div>

            <div class="text-caption text-muted text-uppercase mt-2">Facts</div>
            <div v-for="(fact, index) in preview.facts" :key="index" class="fact d-flex align-center ga-2">
                <span class="flex-grow-1">{{ fact.text }}</span>
                <v-chip size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
                <span class="fact-date">{{ fact.since ? formatDate(worlds.calendar, fact.since) + ' →' : 'always' }}</span>
            </div>

            <!-- what it inherits: the owner can mark a fact the model
                 missed as replaced by one of the preview's own -->
            <template v-if="preview.inherited && preview.inherited.length">
                <div class="text-caption text-muted text-uppercase mt-3">Inherited</div>
                <div
                    v-for="row in preview.inherited"
                    :key="row.fact_id"
                    class="fact inherited d-flex align-center ga-2"
                    data-testid="preview-inherited"
                >
                    <v-checkbox-btn
                        :model-value="overriderOf(row) >= 0"
                        aria-label="Overridden"
                        density="compact"
                        class="flex-grow-0"
                        :disabled="!preview.facts.length"
                        @update:model-value="toggleOverride(row, $event)"
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
                    @click="accept"
                >Accept</v-btn>
                <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" :disabled="!!worlds.pending.accept_preview" @click="worlds.regeneratePreview()">Regenerate</v-btn>
                <v-btn variant="outlined" size="small" prepend-icon="mdi-pencil" :disabled="!!worlds.pending.accept_preview" @click="worlds.discardPreview()">Edit</v-btn>
            </div>
        </v-card>
    </v-card>
</template>

<script>
import { defaultOverrideIndex, heritageFromMatches, sameParents, useWorldsStore } from '@/stores/worlds.js';
import { dateOf, formatDate } from './worldDates.js';
import { kindInfo } from './worldKinds.js';
import HeritagePicker from './HeritagePicker.vue';

const PLACEHOLDERS = {
    character: 'A grizzled ferryman who owes the Wardens more than money…',
    place: 'A half-flooded market town on the river, a little shady…',
    lore: 'The old treaty that sets the river tolls…',
    species: 'Owl-folk: small feathered people with wings instead of arms…',
    race: 'The largest of them, white-plumaged, from the frozen north…',
    mix: 'Anything the blend should settle; the parents are enough to start from…',
};


// how long the prompt rests before its names are looked up
const MATCH_DEBOUNCE_MS = 400;

// The "describe it, then create" box for one kind: a prompt plus the
// optional core-field pickers (born for characters, the parent place for
// places, the heritage picker for characters and mixes). Create shows the
// backend's preview, which can be accepted, regenerated, or dropped to edit
// the prompt and try again.
//
// Heritage: a character's picker is pre-filled from the heritage its
// prompt names, until the owner picks one. Two parents always go through a
// mix: Create asks `find_mix` first; an existing mix becomes the heritage,
// and with none the box drafts the mix in place (a nested mix box, `stay`,
// under the character's own form, which stays on screen untouched) and
// comes back with it picked. A mix box refuses parents
// that already have a mix. `preset` fixes a race's `species` or a mix's
// first parent (the species page's "+ New race" and "+ New mix").
export default {
    name: 'CreateBox',
    components: { HeritagePicker },
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
            matchTimer: null,
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
        // the store's preview request is this box's
        mine() {
            return this.worlds.previewRequest?.kind === this.kind;
        },
        preview() {
            return this.mine ? this.worlds.preview : null;
        },
        busy() {
            return (this.mine && this.worlds.previewPending) || !!this.worlds.pending.accept_preview || this.lookingUp;
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
            if (this.busy || this.mixDraft || !this.validBorn) {
                return false;
            }
            if (this.kind === 'mix') {
                return this.parents.length === 2;
            }
            return !!this.prompt.trim();
        },
        // the prompt's name matches, once looked up
        matches() {
            return this.kind === 'character' ? this.worlds.matchesFor(this.prompt, null) : [];
        },
        // the draft's notice: why it's there, and that the character waits
        mixDraftNotice() {
            const names = this.parents.map((id) => this.heritageName(id) || 'this parent');
            return `${names.join(' and ')} have no mix yet. Every character of two parents shares one mix, so draft it here first; once you accept it, this character carries on with it as heritage.`;
        },
        ownFactItems() {
            return (this.preview?.facts || []).map((fact, index) => ({ title: fact.text, value: index }));
        },
        validBorn() {
            const year = this.bornYear;
            return year === null || year === '' || (Number.isInteger(year) && year >= 1 && year <= 9999);
        },
    },
    watch: {
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
                this.prompt = '';
                this.bornYear = null;
                this.parentId = null;
                this.parents = [...(this.preset.parents || [])];
                this.pickTouched = false;
            }
        },
        prompt() {
            if (this.kind !== 'character' || this.pickTouched) {
                return;
            }
            clearTimeout(this.matchTimer);
            this.matchTimer = setTimeout(() => this.worlds.matchNames(this.prompt, null), MATCH_DEBOUNCE_MS);
        },
        matches(matches) {
            if (!this.pickTouched) {
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
    beforeUnmount() {
        clearTimeout(this.matchTimer);
    },
    methods: {
        formatDate,
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
            this.worlds.previewThing(this.kind, this.prompt.trim(), this.fields());
        },
        accept() {
            this.accepting = this.stay;
            this.worlds.acceptPreview({ name: this.previewName.trim() }, { open: !this.stay });
        },
        cancel() {
            if (this.mine) {
                this.worlds.cancelPreview();
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
        toggleOverride(row, on) {
            this.worlds.setPreviewOverride(row.fact_id, on ? defaultOverrideIndex(this.preview, row) : null);
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
</style>
