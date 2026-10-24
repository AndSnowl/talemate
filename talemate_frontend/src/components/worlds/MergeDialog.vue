<template>
    <v-dialog :model-value="modelValue" max-width="760" scrollable @update:model-value="$event || close()">
        <v-card class="pa-4" data-testid="merge-dialog">
            <div class="d-flex align-center ga-2 mb-2">
                <span class="text-h6">Merge “{{ thing.name }}” into…</span>
                <v-spacer></v-spacer>
                <v-btn icon="mdi-close" variant="text" size="small" aria-label="Close" @click="close"></v-btn>
            </div>
            <div class="text-caption text-muted mb-3">For two entries that turned out to be one thing: every link, filing and field moves over, in one revision, so one undo reverses it.</div>
            <v-autocomplete
                v-model="intoId"
                :items="targets"
                item-title="name"
                item-value="id"
                label="Merge into"
                density="compact"
                variant="outlined"
                hide-details
                data-testid="merge-target"
            >
                <template #item="{ props: itemProps, item }">
                    <v-list-item v-bind="itemProps" :subtitle="item.raw.kind"></v-list-item>
                </template>
            </v-autocomplete>

            <v-alert v-if="worlds.error && modelValue" type="error" variant="tonal" density="compact" class="mt-3">{{ worlds.error }}</v-alert>
            <v-progress-linear v-if="merge && merge.pending" indeterminate color="accent" class="mt-3"></v-progress-linear>

            <template v-if="preview">
                <div class="heading">Name</div>
                <v-radio-group v-model="mainName" density="compact" hide-details data-testid="merge-name">
                    <v-radio v-for="name in preview.names" :key="name" :label="name" :value="name"></v-radio>
                </v-radio-group>
                <div class="text-caption text-muted">The other name becomes an “also known as”.</div>

                <div class="heading">Facts of {{ preview.from_name }}</div>
                <div v-if="!fromFacts.length" class="text-body-2 text-muted">None of its own.</div>
                <div v-for="fact in fromFacts" :key="fact.fact_id" class="fact" data-testid="merge-fact">
                    <div class="d-flex align-center ga-2">
                        <v-checkbox-btn
                            v-model="ticked[fact.fact_id]"
                            density="compact"
                            class="flex-grow-0"
                            :aria-label="'Move over ' + fact.text"
                        ></v-checkbox-btn>
                        <span :class="{ dropped: !ticked[fact.fact_id] }">{{ fact.text }}</span>
                    </div>
                    <div v-if="fact.repeat_of" class="note text-caption">already on {{ fact.repeat_of.owner_name || preview.into_name }}</div>
                </div>

                <template v-if="preview.pairs.length">
                    <div class="heading">These disagree: pick one</div>
                    <div v-for="pair in preview.pairs" :key="pair.key" class="pick" data-testid="merge-pair">
                        <v-radio-group v-model="keep[pair.key]" density="compact" hide-details>
                            <v-radio :label="pairLabel(preview.from_name, pair.a_text, pair.years && pair.years[0])" value="a"></v-radio>
                            <v-radio :label="pairLabel(preview.into_name, pair.b_text, pair.years && pair.years[1])" value="b"></v-radio>
                            <v-radio label="Keep both" value="both"></v-radio>
                        </v-radio-group>
                    </div>
                    <div class="d-flex align-center flex-wrap ga-2 mt-1">
                        <span class="text-caption text-muted">The one not picked:</span>
                        <v-radio-group v-model="lose" inline density="compact" hide-details data-testid="merge-lose">
                            <v-radio label="Remove it" value="remove"></v-radio>
                            <v-radio label="End it" value="end"></v-radio>
                        </v-radio-group>
                    </div>
                </template>

                <template v-if="preview.akas.length">
                    <div class="heading">Other names from its links</div>
                    <div v-for="aka in preview.akas" :key="aka" class="d-flex align-center ga-2" data-testid="merge-aka">
                        <v-checkbox-btn v-model="akas[aka]" density="compact" class="flex-grow-0" :aria-label="'Add the other name ' + aka"></v-checkbox-btn>
                        <span>{{ aka }}</span>
                    </div>
                </template>

                <div class="heading">Links</div>
                <div class="text-body-2 text-muted" data-testid="merge-moves">{{ movesLine }}</div>
                <div v-for="note in preview.notes" :key="note" class="text-caption text-muted">{{ note }}</div>

                <div class="d-flex ga-2 mt-4">
                    <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-call-merge" :loading="!!worlds.pending.accept_merge" :disabled="!mainName" @click="accept">Merge</v-btn>
                    <v-btn variant="text" size="small" :disabled="!!worlds.pending.accept_merge" @click="close">Cancel</v-btn>
                </div>
            </template>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

function plural(count, one, many = `${one}s`) {
    return `${count} ${count === 1 ? one : many}`;
}

// "Merge into…" (curation goal 5): the open entry (`thing`) merged into
// another of its kind the owner picks. The
// preview (`preview_merge`, no model call) gives the dialog: the main name
// (the other becomes an "also known as"); its facts, a repeat of the
// other's unticked ("already on X"); each pair that may disagree, to pick
// one or keep both (keep both to start with: nothing is lost unasked),
// and what the loser gets (removed or ended); the other names its links'
// words would add, each ticked; and what moves over. Merge sends the
// owner's picks (`accept_merge`); the merged entry's page opens.
export default {
    name: 'MergeDialog',
    props: {
        modelValue: { type: Boolean, default: false },
        // the open page's payload: the entry merged away
        thing: { type: Object, required: true },
    },
    emits: ['update:modelValue'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { intoId: null, mainName: null, ticked: {}, keep: {}, lose: 'remove', akas: {}, accepting: false };
    },
    computed: {
        merge() {
            const merge = this.worlds.merge;
            return merge && merge.fromId === this.thing.id ? merge : null;
        },
        preview() {
            return this.merge?.preview || null;
        },
        targets() {
            return this.worlds.referenceTargets.filter((target) => !target.stub && target.id !== this.thing.id && target.kind === this.thing.kind);
        },
        fromFacts() {
            return (this.preview?.facts || []).filter((fact) => fact.side === 'from');
        },
        movesLine() {
            const moves = this.preview?.moves || {};
            const facts = this.fromFacts.filter((fact) => this.ticked[fact.fact_id]).length;
            const parts = [
                plural(facts, 'fact'),
                plural(moves.links || 0, 'link'),
                plural(moves.fields || 0, 'field'),
                plural(moves.filings || 0, 'filing'),
            ];
            return `${parts.join(', ')} move to ${this.preview.into_name}. One undo reverses it.`;
        },
    },
    watch: {
        intoId(id) {
            this.worlds.clearError();
            if (id) {
                this.worlds.previewMerge(this.thing.id, id);
            } else {
                this.worlds.closeMerge();
            }
        },
        // a new preview: the picks start from what it says
        preview(preview, before) {
            if (!preview || preview === before) {
                return;
            }
            if (before && before.from_id === preview.from_id && before.into_id === preview.into_id) {
                return;
            }
            this.mainName = preview.names[0] || null;
            this.ticked = Object.fromEntries(preview.facts.filter((fact) => fact.side === 'from').map((fact) => [fact.fact_id, fact.ticked]));
            this.keep = Object.fromEntries(preview.pairs.map((pair) => [pair.key, 'both']));
            this.lose = 'remove';
            this.akas = Object.fromEntries(preview.akas.map((aka) => [aka, true]));
        },
        // the merge is done (its reply cleared it): the dialog closes
        'worlds.merge'(merge) {
            if (!merge && this.accepting) {
                this.accepting = false;
                this.intoId = null;
                this.$emit('update:modelValue', false);
            }
        },
        'worlds.pending.accept_merge'(now) {
            // failed: the dialog stays, with the error
            if (!now && this.accepting && this.worlds.merge) {
                this.accepting = false;
            }
        },
        modelValue(open) {
            if (open) {
                this.intoId = null;
                this.worlds.clearError();
            }
        },
    },
    methods: {
        pairLabel(name, text, year) {
            return `${name}: ${text}${year ? ` (${year})` : ''}`;
        },
        accept() {
            if (!this.preview || !this.mainName) {
                return;
            }
            this.worlds.clearError();
            this.accepting = true;
            this.worlds.acceptMerge({
                mainName: this.mainName,
                keep: this.keep,
                lose: this.lose,
                akas: this.preview.akas.filter((aka) => this.akas[aka]),
                ticked: this.ticked,
            });
        },
        close() {
            this.intoId = null;
            this.worlds.closeMerge();
            this.$emit('update:modelValue', false);
        },
    },
};
</script>

<style scoped>
.heading {
    margin-top: 14px;
    margin-bottom: 4px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

.fact {
    padding: 2px 0;
}

.dropped {
    color: rgb(var(--v-theme-muted));
}

.note {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}

.pick {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    padding: 4px 10px;
    margin: 6px 0;
}
</style>
