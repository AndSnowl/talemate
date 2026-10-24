<template>
    <div v-if="draft" class="draft-page" data-testid="draft-page">
        <DraftBar :draft="draft" :counts="countsText" :can-accept="!!edited.name.trim()" @accept="accept()" />

        <!-- named like a stub of this kind: fill that stub rather than
             make a second one -->
        <v-alert v-if="matchingStub" type="info" variant="tonal" density="compact" class="mb-2" data-testid="matching-stub">
            <div class="d-flex align-center flex-wrap ga-2">
                <span>There is a stub named “{{ matchingStub.name }}” already.</span>
                <v-spacer></v-spacer>
                <v-btn color="accent" variant="flat" size="small" :loading="draft.accepting" :disabled="!edited.name.trim()" @click="accept(matchingStub.id)">Fill the stub “{{ matchingStub.name }}” instead</v-btn>
            </div>
        </v-alert>
        <v-alert v-if="worlds.previewError" type="error" variant="tonal" density="compact" class="mb-2">{{ worlds.previewError }}</v-alert>

        <!-- the header, as the page's -->
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <v-text-field
                :model-value="edited.name"
                label="Name"
                density="compact"
                variant="outlined"
                hide-details
                class="draft-name"
                data-testid="draft-name"
                @update:model-value="edit({ name: $event })"
            ></v-text-field>
            <v-chip size="x-small" label variant="tonal" color="muted" :prepend-icon="info?.icon" data-testid="thing-kind">{{ edited.kind }}</v-chip>
            <TagChip :tag="edited.tag" local @pick="edit({ tag: $event })" />
            <span v-if="born" class="text-caption text-muted">born <span class="world-date">{{ born }}</span></span>
            <span v-if="edited.hint" class="text-caption text-muted" data-testid="thing-hint">· written with the prompt hint <b>{{ edited.hint }}</b></span>
        </div>

        <!-- 1. In -->
        <DraftIn
            :rows="draftFilings"
            :kept="keptFilings"
            :exclude="ownIds"
            @change="(targetId, change) => edit(changeFiling(edited, targetId, change))"
            @add="edit(addFiling(edited, $event))"
        />

        <!-- 2. Same thing? (only with candidates) -->
        <SameThingAsk
            v-if="!edited.stub_id && edited.same_as && edited.same_as.length"
            :name="edited.name"
            :kind="edited.kind"
            :offers="edited.same_as"
            :verdict="edited.verdict"
            :chosen="edited._same || null"
            :exclude="ownIds"
            @choose="edit({ _same: $event })"
        />

        <!-- 3. Facts, beside the prose -->
        <v-row class="mt-1">
            <v-col cols="12" md="7">
                <div class="d-flex align-center mb-1">
                    <span class="text-overline text-muted">Facts</span>
                    <span class="text-caption text-muted ml-2">{{ tickedCount }} ticked</span>
                    <v-spacer></v-spacer>
                    <EntryAddFacts :thing="pageThing" on-draft />
                </div>
                <div v-if="adding" class="d-flex align-center ga-2 text-caption text-muted mb-1" data-testid="draft-adding">
                    <v-progress-circular indeterminate size="14" width="2" color="accent"></v-progress-circular>
                    Drafting more facts…
                </div>
                <div v-for="row in stubFacts" :key="row.fact_id" class="fact text-muted" data-testid="draft-stub-fact">
                    <LinkedText :segments="row.segments" :text="row.rendered" />
                    <span class="text-caption"> · on the stub already</span>
                </div>
                <div v-if="!factRows.length" class="text-body-2 text-muted">No facts in this draft.</div>
                <div v-for="row in factRows" :key="row.index" class="fact fact-host" data-testid="draft-fact">
                    <div class="d-flex align-center ga-2">
                        <v-checkbox-btn
                            :model-value="row.fact.ticked !== false"
                            density="compact"
                            class="flex-grow-0"
                            :aria-label="'Write ' + row.fact.text"
                            @update:model-value="edit(tickFact(edited, row.index, $event))"
                        ></v-checkbox-btn>
                        <span class="flex-grow-1" :class="{ dropped: row.fact.ticked === false }">
                            <template v-if="editing && editing.index === row.index">
                                <div class="d-flex align-center flex-wrap ga-2">
                                    <v-text-field v-if="editing.mode === 'edit'" v-model="editing.text" label="Fact" density="compact" variant="outlined" hide-details autofocus class="flex-grow-1" @keydown.enter="saveEdit"></v-text-field>
                                    <v-select v-if="editing.mode === 'edit'" v-model="editing.category" :items="categories" label="Category" density="compact" variant="outlined" hide-details class="category"></v-select>
                                    <v-text-field v-if="editing.mode === 'dates'" v-model.number="editing.year" label="From year" type="number" density="compact" variant="outlined" hide-details class="year" @keydown.enter="saveEdit"></v-text-field>
                                    <v-btn color="accent" variant="flat" size="small" @click="saveEdit">Save</v-btn>
                                    <v-btn variant="text" size="small" @click="editing = null">Cancel</v-btn>
                                </div>
                            </template>
                            <template v-else>
                                <LinkedText class="fact-text" :segments="row.segments" :text="row.fact.text" selectable @select="selected(row, $event)" />
                                <span v-if="row.fact.held_by" class="held" data-testid="held-by-tag">held by {{ row.fact.held_by_name || 'another entry' }}<v-btn
                                    icon="mdi-close"
                                    variant="text"
                                    size="x-small"
                                    density="compact"
                                    :aria-label="'Not held: ' + row.fact.text"
                                    @click="edit(holdFact(edited, row.index, null))"
                                ></v-btn></span>
                                <span v-if="row.local" class="text-caption text-muted"> · added here</span>
                            </template>
                        </span>
                        <v-chip size="x-small" label variant="tonal" color="muted">{{ row.fact.category }}</v-chip>
                        <span class="fact-date">{{ row.fact.since ? formatDate(worlds.calendar, row.fact.since) + ' →' : 'always' }}</span>
                        <FactRowActions
                            :fact="row.fact"
                            draft
                            :exclude="ownIds"
                            @edit="startEdit(row, 'edit')"
                            @dates="startEdit(row, 'dates')"
                            @remove="edit(removeFact(edited, row.index))"
                            @move="edit(moveFactTo(edited, row.index, $event))"
                            @copy="edit(copyFactTo(edited, row.index, $event))"
                            @held="edit(holdFact(edited, row.index, $event))"
                        />
                    </div>
                    <PreviewRepeats
                        v-if="row.fact.repeat_of"
                        :repeat="row.fact.repeat_of"
                        :ticked="row.fact.ticked !== false"
                        :moving="!!row.fact.moveRepeat"
                        @settle="edit(settleRepeat(edited, row.index, $event))"
                    />
                </div>

                <!-- what it inherits, each ticked as kept: unticking one the
                     model missed marks it replaced by one of its own -->
                <template v-if="edited.inherited && edited.inherited.length">
                    <div class="text-caption text-muted text-uppercase mt-3">Inherited (untick to replace)</div>
                    <div v-for="row in edited.inherited" :key="row.fact_id" class="fact inherited d-flex align-center ga-2" data-testid="preview-inherited">
                        <v-checkbox-btn
                            :model-value="overriderOf(row) < 0"
                            aria-label="Kept"
                            density="compact"
                            class="flex-grow-0"
                            :disabled="!edited.facts.length"
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
            </v-col>
            <v-col cols="12" md="5">
                <div v-for="(text, section) in edited.prose" :key="section" class="mb-3" data-testid="draft-prose">
                    <div class="text-overline text-muted">{{ section }} (generated)</div>
                    <div class="prose pa-3">
                        <LinkedText v-if="text" :segments="(draft.page.prose_segments || {})[section]" :text="text" />
                        <span v-else class="text-muted">Not written yet.</span>
                    </div>
                </div>
            </v-col>
        </v-row>

        <!-- 4. For other pages -->
        <PreviewElsewhere
            :rows="edited.elsewhere || []"
            type="create"
            :new-names="edited.new_names || []"
            :also-here="ownTexts"
            :exclude="ownIds"
            @update="edit({ elsewhere: $event })"
            @retarget="(index, target) => edit(retarget(edited, index, target))"
            @also="edit(alsoHere(edited, $event))"
        />

        <!-- 5. Could move here -->
        <MoveHere :draft="edited" @tick="tickMove" />

        <!-- 6. New names -->
        <PreviewStubs :rows="edited.new_names || []" @change="(name, change) => edit(changeNewName(edited, name, change))" />

        <!-- 7. File into this -->
        <div v-if="(edited.file_into || []).length" class="mt-3" data-testid="draft-file-into">
            <div class="heading">File into this <span class="text-muted">· entries that look like they belong in it</span></div>
            <div v-for="row in edited.file_into" :key="row.thing_id" class="d-flex align-center ga-2" data-testid="file-into-row">
                <v-checkbox-btn
                    :model-value="!!row.ticked"
                    density="compact"
                    class="flex-grow-0"
                    :aria-label="'File ' + row.name + ' into this'"
                    @update:model-value="edit(tickFileInto(edited, row.thing_id, $event))"
                ></v-checkbox-btn>
                <span class="target" :class="{ dropped: !row.ticked }">{{ row.name }}</span>
                <span v-if="row.role" class="role">{{ row.role }}</span>
            </div>
        </div>

        <EntryTimeline :lines="draft.page.entry_timeline || []" class="mt-4">
            <template #actions>
                <EntryAddFacts :thing="pageThing" event on-draft />
            </template>
        </EntryTimeline>

        <SelectionMenu
            v-model="selecting"
            :target="selection?.target"
            :words="selection?.words || ''"
            :blocked="selection?.blocked || ''"
            :exclude="ownIds"
            draft
            @stub="selectionStub"
            @link="selectionLink"
        />
    </div>
</template>

<script>
import { countsLine, defaultOverrideIndex, moveInEdit, previewCounts, useWorldsStore } from '@/stores/worlds.js';
import {
    addFiling,
    alsoHere,
    changeFiling,
    changeNewName,
    copyFactTo,
    draftFactRows,
    editFact,
    holdFact,
    moveFactTo,
    removeFact,
    retarget,
    settleRepeat,
    tickFact,
    tickFileInto,
    tickMoveHere,
} from './draftPage.js';
import { dateOf, formatDate } from './worldDates.js';
import { kindInfo } from './worldKinds.js';
import DraftBar from './DraftBar.vue';
import DraftIn from './DraftIn.vue';
import EntryAddFacts from './EntryAddFacts.vue';
import EntryTimeline from './EntryTimeline.vue';
import FactRowActions from './FactRowActions.vue';
import LinkedText from './LinkedText.vue';
import MoveHere from './MoveHere.vue';
import PreviewElsewhere from './PreviewElsewhere.vue';
import PreviewRepeats from './PreviewRepeats.vue';
import PreviewStubs from './PreviewStubs.vue';
import SameThingAsk from './SameThingAsk.vue';
import SelectionMenu from './SelectionMenu.vue';
import TagChip from './TagChip.vue';

// The draft page: the entry page's draft mode (spec "The draft page",
// mockup v2 screens 3 and 4, v3 screen C). A new or expanded entry opens
// as the page it will be, marked as a draft, and nothing is written until
// Accept. Under its bar (`DraftBar`) come its header (the name to edit,
// its kind, its tag chip, its prompt hint), then, in the spec's order:
// 1. In (`DraftIn`: the AI's filings unticked, ruling F7; "+ in… 🔎" the
//    owner's own, ticked);
// 2. "Same thing?" (`SameThingAsk`: a search, empty for new; only with
//    candidates);
// 3. Facts, each ticked as it came, with its menu (`FactRowActions` in
//    draft mode) and a repeat's "Move that one here", "Keep both" or
//    "Drop this" (`PreviewRepeats`), then what it inherits; its prose
//    beside them; "+ Add facts…" and "+ Add event…" add to the draft;
// 4. For other pages (`PreviewElsewhere`: a row's target changed, "+ also
//    here");
// 5. Could move here (`MoveHere`, unticked, its names highlighted);
// 6. New names (`PreviewStubs`: kind, tag, same as… 🔎, in… 🔎, rename
//    for later);
// 7. File into this (unticked);
// and its Timeline. Right-clicking selected words of a drafted fact opens
// the selection menu (ruling F16: a stub or a link keyed by the words, so
// every place the draft writes them; on the server's copy, `index` the
// fact's there). The owner's edits stay in the store (`worlds.draft`,
// `editDraft`) and go with Accept; the draft's own logic is draftPage.js.
// `stay` (a nested mix box): accepting doesn't open the new page.
export default {
    name: 'DraftPage',
    components: {
        DraftBar,
        DraftIn,
        EntryAddFacts,
        EntryTimeline,
        FactRowActions,
        LinkedText,
        MoveHere,
        PreviewElsewhere,
        PreviewRepeats,
        PreviewStubs,
        SameThingAsk,
        SelectionMenu,
        TagChip,
    },
    props: {
        stay: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // a fact being edited here: `{index, mode: 'edit'|'dates', text, category, year}`
            editing: null,
            // selected words: `{index, start, end, words, target, blocked}`
            selection: null,
            selecting: false,
        };
    },
    computed: {
        draft() {
            return this.worlds.draft;
        },
        edited() {
            return this.draft.edited;
        },
        info() {
            return kindInfo(this.edited.kind);
        },
        categories() {
            return this.info?.categories || [];
        },
        // the page EntryAddFacts asks about (a draft has no id until it's made)
        pageThing() {
            return { id: this.draft.page.id, at: null };
        },
        adding() {
            return !!this.draft.adding;
        },
        // the stub it expands, and the entries never offered as targets
        ownIds() {
            return this.edited.stub_id ? [this.edited.stub_id] : [];
        },
        born() {
            const born = this.edited.fields?.born;
            return born && typeof born === 'object' ? formatDate(this.worlds.calendar, born) : null;
        },
        // a stub's own filings and facts, written already
        keptFilings() {
            return (this.draft.page.in || []).filter((row) => !row.draft);
        },
        // its own "In" rows: not one the stub has already
        draftFilings() {
            const kept = new Set(this.keptFilings.map((row) => row.target_id));
            return (this.edited.filings || []).filter((row) => !kept.has(row.target_id));
        },
        stubFacts() {
            return (this.draft.page.facts || []).filter((fact) => !fact.draft);
        },
        factRows() {
            return draftFactRows(this.draft.page, this.edited);
        },
        ownTexts() {
            return this.factRows.map((row) => row.fact.text);
        },
        tickedCount() {
            return this.factRows.filter((row) => row.fact.ticked !== false).length;
        },
        ownFactItems() {
            return (this.edited.facts || []).flatMap((fact, index) => (fact.removed ? [] : [{ title: fact.text, value: index }]));
        },
        // the stub of this kind it's named like (not one it expands)
        matchingStub() {
            const id = this.edited.matching_stub_id;
            if (!id || this.edited.stub_id) {
                return null;
            }
            return { id, name: this.worlds.stubInfo(id)?.name || this.edited.name };
        },
        countsText() {
            const same = this.edited._same;
            const onto = same
                ? (this.edited.same_as || []).find((offer) => offer.thing_id === same)?.name
                    || this.worlds.referenceTargets.find((target) => target.id === same)?.name
                : null;
            return countsLine(previewCounts(this.edited), onto);
        },
    },
    watch: {
        'draft.version'() {
            this.editing = null;
            this.selecting = false;
        },
    },
    methods: {
        formatDate,
        addFiling,
        alsoHere,
        changeFiling,
        changeNewName,
        copyFactTo,
        holdFact,
        moveFactTo,
        removeFact,
        retarget,
        settleRepeat,
        tickFact,
        tickFileInto,
        edit(changes) {
            this.worlds.editDraft(changes);
        },
        tickMove(factId, ticked) {
            const rows = tickMoveHere(this.edited, factId, ticked).move_here;
            this.edit(moveInEdit(this.edited, rows));
        },
        accept(intoStub = null) {
            this.worlds.acceptPreview(
                { name: this.edited.name.trim() },
                { open: !this.stay, intoStub, sameTargetId: intoStub ? null : this.edited._same || null },
            );
        },
        startEdit(row, mode) {
            const since = row.fact.since;
            this.editing = {
                index: row.index,
                mode,
                text: row.fact.text,
                category: row.fact.category,
                year: since ? Number(String(since.label || '').match(/\d+/)?.[0]) || null : null,
            };
        },
        saveEdit() {
            const found = this.editing;
            if (!found) {
                return;
            }
            if (found.mode === 'edit') {
                if (found.text.trim()) {
                    this.edit(editFact(this.edited, found.index, { text: found.text.trim(), category: found.category }));
                }
            } else {
                const year = Number.isInteger(found.year) && found.year >= 1 && found.year <= 9999 ? found.year : null;
                this.edit(editFact(this.edited, found.index, { since: year ? dateOf(year) : null }));
            }
            this.editing = null;
        },
        // words selected in a drafted fact: the server's copy is what a
        // selection names, so a fact written or rewritten here has none
        selected(row, { start, end, words, x, y }) {
            this.selection = {
                index: row.serverIndex,
                start,
                end,
                words,
                target: [x, y],
                blocked: row.serverIndex === null ? 'This fact was written or changed here: its words can be linked once it\'s accepted.' : '',
            };
            this.selecting = true;
        },
        selectionStub({ kind, tag }) {
            const found = this.selection;
            if (found && found.index !== null) {
                this.worlds.draftSelection('make_stub_from_text', found.index, found.start, found.end, { kind, ...(tag ? { tag } : {}) });
            }
        },
        selectionLink(target) {
            const found = this.selection;
            if (found && found.index !== null) {
                this.worlds.draftSelection('link_text', found.index, found.start, found.end, { target_id: target.id });
            }
        },
        // the own fact replacing the inherited `row`, or -1
        overriderOf(row) {
            return this.edited.facts.findIndex((fact) => !fact.removed && (fact.overrides || []).includes(row.fact_id));
        },
        // ticked: inherited as it is; unticked: replaced by an own fact
        setKept(row, kept) {
            this.worlds.setPreviewOverride(row.fact_id, kept ? null : defaultOverrideIndex(this.edited, row));
        },
    },
};
</script>

<style scoped>
.draft-name {
    max-width: 340px;
}

.world-date {
    color: rgb(var(--v-theme-date));
}

.heading {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

.fact {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 3px 0;
}

.fact .v-chip,
.fact .v-btn {
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

.dropped {
    color: rgb(var(--v-theme-muted));
}

.held {
    margin-left: 6px;
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}

.inherited {
    color: rgb(var(--v-theme-muted));
}

.replaced {
    text-decoration: line-through;
    color: rgb(var(--v-theme-muted));
}

.override-by {
    flex: none;
    width: 220px;
}

.category {
    flex: none;
    width: 150px;
}

.year {
    flex: none;
    width: 120px;
}

.prose {
    background: rgb(var(--v-theme-raised));
    border-radius: 6px;
    line-height: 1.5;
    white-space: pre-wrap;
}

.target {
    font-weight: 600;
    color: rgb(var(--v-theme-link));
}

.role {
    font-style: italic;
    color: rgb(var(--v-theme-muted));
}
</style>
