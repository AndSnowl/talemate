<template>
    <div class="drawer-add-form my-2" data-testid="drawer-add-form" @keydown.esc="$emit('close')">
        <template v-if="drawer.type === 'people'">
            <div class="d-flex align-center flex-wrap ga-2">
                <v-autocomplete v-model="characterId" :items="characterOptions" item-title="name" item-value="id" label="Character" density="compact" variant="outlined" hide-details class="picker"></v-autocomplete>
                <v-text-field v-model="role" label="Role" density="compact" variant="outlined" hide-details class="picker"></v-text-field>
                <v-text-field v-model.number="year" label="Since (year)" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year"></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!canSave" @click="save">Add</v-btn>
                <v-btn variant="text" size="small" @click="$emit('close')">Cancel</v-btn>
            </div>
        </template>
        <template v-else-if="drawer.type === 'branches'">
            <div class="d-flex align-center flex-wrap ga-2">
                <v-text-field
                    v-model="prompt"
                    label="Describe the branch"
                    placeholder="The Reformed Dawn, who reject the doctrine of snowy superiority…"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="flex-grow-1"
                    @keydown.enter="save"
                ></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!canSave" @click="save">Preview</v-btn>
                <v-btn variant="text" size="small" @click="$emit('close')">Cancel</v-btn>
            </div>
        </template>
        <template v-else>
            <v-btn-toggle v-model="mode" density="compact" variant="outlined" divided mandatory class="mb-2" data-testid="drawer-add-mode">
                <v-btn value="statement" size="small">Write a statement</v-btn>
                <v-btn value="entry" size="small">File an entry</v-btn>
            </v-btn-toggle>
            <NameHighlightInput
                v-if="mode === 'statement'"
                v-model="text"
                v-model:picks="picks"
                v-model:refs="refs"
                label="Statement"
                :rows="1"
                dense
                :at="worlds.thingAt"
                :exclude="[thing.id]"
                class="mb-2"
            />
            <div class="d-flex align-center flex-wrap ga-2">
                <v-autocomplete v-if="mode === 'entry'" v-model="thingId" :items="entryOptions" item-title="name" item-value="id" label="File an entry here" density="compact" variant="outlined" hide-details class="picker"></v-autocomplete>
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!canSave" @click="save">Add</v-btn>
                <v-btn variant="text" size="small" @click="$emit('close')">Cancel</v-btn>
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf } from './worldDates.js';
import { PART_OF_KINDS, actsInWorld, drawerTypesFor } from './worldKinds.js';
import { factLinkPayload } from './nameHighlights.js';
import NameHighlightInput from './NameHighlightInput.vue';

function validYear(year) {
    return Number.isInteger(year) && year >= 1 && year <= 9999;
}

// A drawer's "+ Add", by type:
// - people: a character (or real being), a role and a year it's tied from (`worlds.addTie`,
//   written from the character's side);
// - branches: the new branch's prompt (`worlds.previewBranch`);
// - any other: a statement written by hand (`add_statement`, its names
//   highlighted and linked as a fact's are) or an existing entry filed here
//   (`set_part_of`, offering only kinds this drawer may hold).
// `close` when it's done (the page's reply), cancelled, or Esc.
export default {
    name: 'DrawerAddForm',
    components: { NameHighlightInput },
    props: {
        drawer: { type: Object, required: true },
        // the sphere's thing payload
        thing: { type: Object, required: true },
    },
    emits: ['close'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            mode: 'statement',
            characterId: null,
            role: '',
            year: null,
            prompt: '',
            thingId: null,
            text: '',
            picks: {},
            refs: {},
        };
    },
    computed: {
        // characters and real beings (only those can be tied), not tied
        // already
        characterOptions() {
            const tied = new Set(this.thing.sphere.people.map((person) => person.character_id));
            const beings = (this.worlds.things.being || []).filter((thing) => !thing.stub && actsInWorld(thing));
            return [...(this.worlds.things.character || []), ...beings].filter((thing) => !tied.has(thing.id));
        },
        // entries this drawer may hold, not in it already, not the sphere
        entryOptions() {
            const held = new Set(this.drawer.items.map((item) => item.thing_id));
            return this.worlds.referenceTargets.filter(
                (target) => PART_OF_KINDS.includes(target.kind)
                    && drawerTypesFor(target.kind).includes(this.drawer.type)
                    && !held.has(target.id)
                    && target.id !== this.thing.id,
            );
        },
        busy() {
            const pending = this.worlds.pending;
            return !!(pending.set_part_of || pending.set_ties || pending.add_statement || this.worlds.branchPending);
        },
        canSave() {
            if (this.busy) {
                return false;
            }
            if (this.drawer.type === 'people') {
                return !!this.characterId && (this.year === null || this.year === '' || validYear(this.year));
            }
            if (this.drawer.type === 'branches') {
                return !!this.prompt.trim();
            }
            return this.mode === 'entry' ? !!this.thingId : !!this.text.trim();
        },
    },
    watch: {
        // the page's reply: done (a branch closes once its preview is in)
        thing() {
            if (this.drawer.type !== 'branches') {
                this.$emit('close');
            }
        },
        'worlds.branchPending'(now, before) {
            if (before && !now && this.drawer.type === 'branches') {
                this.$emit('close');
            }
        },
    },
    methods: {
        save() {
            if (!this.canSave) {
                return;
            }
            const sphereId = this.thing.id;
            if (this.drawer.type === 'people') {
                this.worlds.addTie(this.characterId, {
                    sphere_id: sphereId,
                    role: this.role.trim(),
                    since: validYear(this.year) ? dateOf(this.year) : null,
                });
            } else if (this.drawer.type === 'branches') {
                this.worlds.previewBranch(sphereId, this.prompt.trim());
            } else if (this.mode === 'entry') {
                this.worlds.setPartOf(this.thingId, sphereId, this.drawer.id);
            } else {
                const text = this.text.trim();
                const matches = this.worlds.matchesFor(this.text, this.worlds.thingAt);
                this.worlds.addStatement(sphereId, this.drawer.id, text, factLinkPayload(text, matches, this.picks, this.refs, []));
            }
        },
    },
};
</script>

<style scoped>
.picker {
    min-width: 220px;
    max-width: 280px;
}

.year {
    max-width: 150px;
}
</style>
