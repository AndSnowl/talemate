<template>
    <div class="thing-page" data-testid="thing-page">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <v-btn variant="text" size="small" prepend-icon="mdi-arrow-left" data-testid="thing-back" @click="worlds.goBack()">Back</v-btn>
            <template v-if="thing">
                <div v-if="rename" class="d-flex align-center ga-2" data-testid="rename-field">
                    <v-text-field
                        v-model="rename.text"
                        label="Name"
                        density="compact"
                        variant="outlined"
                        hide-details
                        autofocus
                        class="rename-input"
                        :disabled="rename.sent"
                        @keydown.enter="saveRename"
                        @keydown.esc="rename = null"
                    ></v-text-field>
                    <v-btn color="accent" variant="flat" size="small" :loading="rename.sent" :disabled="!rename.text.trim()" @click="saveRename">Save</v-btn>
                    <v-btn variant="text" size="small" :disabled="rename.sent" @click="rename = null">Cancel</v-btn>
                </div>
                <template v-else>
                    <span class="text-h5 thing-name" data-testid="thing-name">{{ thing.name }}</span>
                    <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Rename" data-testid="rename-thing" @click="startRename"></v-btn>
                </template>
                <v-chip v-if="!thing.sphere || thing.kind !== 'sphere'" size="x-small" label variant="tonal" color="muted" :prepend-icon="info?.icon" data-testid="thing-kind">{{ thing.kind }}</v-chip>
                <template v-if="thing.sphere">
                    <v-chip size="x-small" label variant="outlined" prepend-icon="mdi-orbit" data-testid="sphere-template">sphere{{ thing.sphere.template ? ' · ' + thing.sphere.template : '' }}</v-chip>
                    <v-chip
                        size="x-small"
                        label
                        variant="outlined"
                        data-testid="sphere-agent"
                        :title="thing.sphere.agent ? 'It acts in the world (click: a body of knowledge)' : 'A body of knowledge (click: it acts in the world)'"
                        :disabled="!!worlds.pending.set_field"
                        @click="worlds.setField('agent', !thing.sphere.agent)"
                    >{{ thing.sphere.agent ? 'acts in the world' : 'a body of knowledge' }}</v-chip>
                </template>
                <v-spacer></v-spacer>

                <v-btn
                    v-if="canPromote(thing)"
                    variant="outlined"
                    size="small"
                    prepend-icon="mdi-orbit"
                    data-testid="make-sphere"
                    @click="worlds.makeSphere(thing)"
                >Make it a sphere…</v-btn>

                <v-menu v-model="asOfMenu" :close-on-content-click="false" location="bottom end">
                    <template #activator="{ props }">
                        <v-btn v-bind="props" variant="outlined" size="small" append-icon="mdi-menu-down" data-testid="as-of-button" @click="openAsOf">
                            viewing:&nbsp;<span class="world-date">{{ viewingLabel }}</span>
                        </v-btn>
                    </template>
                    <v-card class="pa-3" min-width="260" data-testid="as-of-picker">
                        <div class="text-caption text-muted mb-2">View this {{ info?.singular || 'thing' }} as of a date</div>
                        <div class="d-flex ga-2">
                            <v-text-field v-model.number="asOfYear" label="Year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details></v-text-field>
                            <v-select v-model="asOfMonth" label="Month" :items="monthOptions" item-title="title" item-value="value" clearable density="compact" variant="outlined" hide-details></v-select>
                        </div>
                        <div class="d-flex ga-2 mt-3">
                            <v-btn color="accent" variant="flat" size="small" :disabled="!validYear(asOfYear)" @click="applyAsOf">View</v-btn>
                            <v-btn variant="text" size="small" @click="viewAt(null)">Latest</v-btn>
                        </div>
                    </v-card>
                </v-menu>

                <v-btn
                    v-if="!thing.stub"
                    variant="outlined"
                    size="small"
                    prepend-icon="mdi-refresh"
                    :loading="worlds.proseRegenerating === thing.id && !worlds.proseRegeneratingSection"
                    :disabled="worlds.proseRegenerating === thing.id"
                    @click="worlds.regenerateProse()"
                >Regenerate prose</v-btn>

                <v-btn
                    variant="outlined"
                    size="small"
                    color="danger"
                    prepend-icon="mdi-delete"
                    data-testid="delete-thing"
                    :loading="!!worlds.pending.thing_references"
                    @click="worlds.requestDelete()"
                >Delete</v-btn>
            </template>
        </div>

        <div v-if="!thing" class="d-flex justify-center pa-8">
            <v-progress-circular indeterminate color="accent"></v-progress-circular>
        </div>

        <template v-else>
            <div v-if="thing.stub" class="stub-panel pa-3 mb-4" data-testid="stub-panel">
                <div class="text-subtitle-2 mb-1">A stub</div>
                <StubCard :stub="stubOfPage" on-page />
            </div>

            <div class="timeline-strip d-flex flex-wrap align-center ga-1 mb-4" data-testid="timeline-strip">
                <v-chip
                    v-for="(point, index) in timelinePoints"
                    :key="index"
                    size="small"
                    :variant="point.reached ? 'tonal' : 'outlined'"
                    :color="point.scene ? 'scene' : (point.reached ? 'date' : 'muted')"
                    :prepend-icon="point.scene ? 'mdi-movie-open' : undefined"
                    @click="viewAt(point.date)"
                >
                    <span class="point-date">{{ point.dateLabel }}</span>
                    <span class="point-text">{{ point.text }}</span>
                </v-chip>
                <v-chip size="small" :variant="thing.at ? 'outlined' : 'tonal'" color="date" @click="viewAt(null)">latest</v-chip>
            </div>

            <SpherePage v-if="thing.sphere" />

            <v-row>
                <v-col cols="12" md="6">
                    <div v-for="field in shownFields" :key="field.name" class="field d-flex align-center flex-wrap ga-2" :data-testid="'field-' + field.name">
                        <span class="field-label">{{ field.label }}</span>
                        <span v-if="field.links">
                            <template v-for="(link, index) in field.links" :key="link.id">
                                <span v-if="index" class="text-muted"> · </span>
                                <a class="thing-link" href="#" @click.prevent="worlds.openThing(link.id)">{{ link.name }}</a>
                            </template>
                        </span>
                        <span v-else :class="{ 'text-muted': field.deleted }">{{ field.text }}</span>
                        <v-chip v-if="field.pastLifespan" size="x-small" label variant="tonal" color="warning" prepend-icon="mdi-alert" data-testid="past-lifespan">past lifespan</v-chip>
                        <span v-if="field.note" class="text-caption text-muted">{{ field.note }}</span>
                    </div>
                    <PartOfLine v-if="hasPartOf" :thing="thing" />
                    <ThingNumbers v-if="isHeritage" />
                    <ThingAka />

                    <!-- a pure sphere's facts all show in its sphere part -->
                    <template v-if="thing.kind !== 'sphere'">
                    <div class="d-flex align-center mt-4 mb-1">
                        <span class="text-overline text-muted">{{ showInherited ? 'Own facts' : 'Facts' }}</span>
                        <v-spacer></v-spacer>
                        <v-btn v-if="!form || form.factId" variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="startAdd">Add fact</v-btn>
                    </div>

                    <div v-if="form && !form.factId && !form.anchor" class="mb-2">
                        <ThingFactForm :form="form" :categories="categories" :busy="editing" @save="saveForm" @cancel="form = null" />
                    </div>

                    <div v-if="!shownFacts.length" class="text-body-2 text-muted">No facts true at this date.</div>
                    <template v-for="fact in shownFacts" :key="fact.fact_id">
                        <div class="fact d-flex align-center ga-2" data-testid="fact-row">
                            <span class="flex-grow-1">
                                <LinkedText :segments="fact.segments" :text="fact.rendered" repoint :exclude="[thing.id]" @repoint="repointLink(fact, $event)" />
                                <span v-for="note in overrideNotes(fact)" :key="note" class="override-note">(overrides {{ note }})</span>
                            </span>
                            <v-chip size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
                            <span class="fact-date">{{ spanLabel(worlds.calendar, fact.valid_from, fact.valid_until) }}</span>
                            <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit fact" @click="startEdit(fact)"></v-btn>
                            <v-btn v-if="!fact.valid_until" icon="mdi-timer-off-outline" variant="text" size="x-small" density="comfortable" aria-label="End fact" @click="startEnd(fact)"></v-btn>
                        </div>
                        <div v-if="form && form.factId === fact.fact_id" class="my-2">
                            <ThingFactForm :form="form" :categories="categories" :busy="editing" @save="saveForm" @cancel="form = null" @remove="removeFact(fact)" />
                        </div>
                    </template>
                    </template>

                    <ThingInherited
                        v-if="showInherited"
                        :inherited="thing.inherited"
                        :form="form"
                        :categories="categories"
                        :busy="editing"
                        @override="startOverride"
                        @save="saveForm"
                        @cancel="form = null"
                    />
                    <TiesSection v-if="thing.kind === 'character'" :thing="thing" />
                    <HeritageSections v-if="thing.kind === 'species'" :species-id="thing.id" :races="thing.races" :mixes="thing.mixes" />
                    <NamedStubs :stubs="thing.named_stubs || []" />
                </v-col>

                <v-col cols="12" md="6">
                    <div v-if="thing.stub" data-testid="stub-mentions-list">
                        <div class="text-overline text-muted">Mentioned in</div>
                        <div v-if="!thing.mentions.length" class="text-body-2 text-muted">Nothing mentions it now.</div>
                        <div v-for="mention in thing.mentions" :key="mention.fact_id" class="fact" data-testid="stub-mention">
                            <a class="thing-link" href="#" @click.prevent="worlds.openThing(mention.owner_id)">{{ mention.owner_name }}</a>
                            <span class="text-caption text-muted"> ({{ mention.category }})</span>:
                            {{ mention.text }}
                        </div>
                    </div>
                    <div v-for="(prose, section) in proseShown" :key="section" class="mb-3">
                        <div class="d-flex align-center ga-2">
                            <span class="text-overline text-muted">{{ section }} (generated)</span>
                            <v-chip v-if="prose.stale" size="x-small" label variant="tonal" color="warning">out of date</v-chip>
                            <v-spacer></v-spacer>
                            <v-btn
                                v-if="proseSectionCount > 1"
                                variant="text"
                                size="x-small"
                                prepend-icon="mdi-refresh"
                                :aria-label="'Regenerate ' + section"
                                :data-testid="'regenerate-' + section"
                                :loading="worlds.proseRegenerating === thing.id && worlds.proseRegeneratingSection === section"
                                :disabled="worlds.proseRegenerating === thing.id"
                                @click="worlds.regenerateProse(section)"
                            >Regenerate</v-btn>
                        </div>
                        <div class="prose pa-3">
                            <LinkedText v-if="prose.text" :segments="(thing.prose_segments || {})[section]" :text="prose.text" />
                            <span v-else class="text-muted">Not written yet.</span>
                        </div>
                    </div>

                    <ThingReferencedIn v-if="isHeritage" :references="thing.referenced_in" @view-at="viewAt" />
                    <template v-else>
                        <div class="text-overline text-muted">Appears in</div>
                        <div v-if="!thing.appears_in.length" class="text-body-2 text-muted">No scenes yet.</div>
                        <div v-else class="d-flex flex-wrap ga-2">
                            <v-chip v-for="scene in thing.appears_in" :key="scene.id" size="small" variant="tonal" color="scene" prepend-icon="mdi-movie-open" @click="viewAt(scene.start)">
                                {{ scene.name }}&nbsp;<span class="text-muted">· {{ formatDate(worlds.calendar, scene.start) }}</span>
                            </v-chip>
                        </div>
                    </template>
                </v-col>
            </v-row>
        </template>

        <ThingDeleteDialog />
    </div>
</template>

<script>
import { listedFacts, useWorldsStore } from '@/stores/worlds.js';
import { ageAt, dateOf, dateParts, formatDate, spanLabel } from './worldDates.js';
import { HERITAGE_KINDS, INHERITING_KINDS, PART_OF_KINDS, canPromote, kindInfo, overrideCategory } from './worldKinds.js';
import { formatNumber } from './worldNumbers.js';
import { NEW_THING, factEditState, factLinkPayload, refOccurrence, repicks } from './nameHighlights.js';
import HeritageSections from './HeritageSections.vue';
import LinkedText from './LinkedText.vue';
import NamedStubs from './NamedStubs.vue';
import PartOfLine from './PartOfLine.vue';
import SpherePage from './SpherePage.vue';
import StubCard from './StubCard.vue';
import ThingAka from './ThingAka.vue';
import ThingDeleteDialog from './ThingDeleteDialog.vue';
import ThingFactForm from './ThingFactForm.vue';
import ThingInherited from './ThingInherited.vue';
import ThingNumbers from './ThingNumbers.vue';
import ThingReferencedIn from './ThingReferencedIn.vue';
import TiesSection from './TiesSection.vue';

// fields shown elsewhere (the name; a heritage kind's numbers; a sphere's
// template, agent flag, drawers and branch parent; part of; ties), not
// shown in the slice (cultures, languages, a branch's drops), or not for
// reading (voice, colour)
const HIDDEN_FIELDS = [
    'name', 'culture', 'cultures', 'voice', 'color', 'lifespan', 'adult_age', 'measures',
    'template', 'agent', 'drawers', 'part_of', 'ties', 'drops', 'language',
];

const FIELD_LABELS = {
    born: 'Born',
    kind: 'Kind',
    parent: 'Inside',
    owner: 'Owner',
    place: 'Place',
    when: 'When',
    until: 'Until',
    heritage: 'Heritage',
    species: 'Species',
    parents: 'Parents',
    origin: 'Origin',
};

const EDIT_ACTIONS = ['add_fact', 'correct_fact', 'end_fact', 'remove_fact', 'override_fact'];

const THING_ID = /^[0-9a-f]{32}$/;

function yearOf(date) {
    return date ? dateParts(date).year : null;
}

function cut(text, length = 28) {
    return text.length > length ? text.slice(0, length - 1).trimEnd() + '…' : text;
}

// A thing's page: its name (renamed in place), core fields, the facts true
// at the viewing date (add, edit, end), the generated prose with
// Regenerate (every section, or one of a character's), the "viewing as of"
// date, a timeline strip of its dated changes and scenes, the scenes it
// appears in, and Delete (after a reference check and a confirmation).
// A character's heritage shows as links, with its life stage by its age.
// A species, race or mix page has its numbers, and what references it in
// place of the scenes. A character, race or mix page shows what it
// inherits, each fact open to an override; a species page its races and
// mixes. Facts, inherited facts and prose show their names linked
// (`LinkedText`), and an own fact's link can be re-pointed at another
// thing (`repoint_ref`: that one reference, its words kept, nothing else
// changed); the page lists its other names (`ThingAka`) and the stubs its
// facts named (`NamedStubs`). The fact form edits a fact's words as they
// read, its links kept by position (`factEditState`): saving sends them
// as `spans`, each to its own thing, then the owner's picks and names
// treated as new. Once the save is answered, the things the owner
// re-picked are taught their names as written, and the stubs the owner
// asked for are made (`make_stub`, which links just that phrase). A stub's
// page has no prose: its card (kind, Expand, Ignore) and what mentions it
// instead.
//
// Spheres: a sphere (or a place that took on a template) shows its
// template and agent chips (the agent flag toggles) and its sphere part
// (`SpherePage`: summary, drawers, Timeline, Branches); an entry a sphere
// can hold has a "Part of" line (`PartOfLine`); a character its Ties
// (`TiesSection`), its "but…" facts shown there rather than among its
// facts. "Make it a sphere…" shows on a lore entry, a place that isn't a
// sphere and a stub (`worlds.makeSphere`).
export default {
    name: 'ThingPage',
    components: {
        HeritageSections,
        LinkedText,
        NamedStubs,
        StubCard,
        ThingAka,
        ThingDeleteDialog,
        ThingFactForm,
        ThingInherited,
        ThingNumbers,
        ThingReferencedIn,
        TiesSection,
        PartOfLine,
        SpherePage,
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    // the page's fact form, for the sphere part's own facts (drawer
    // statements, Timeline rows, about facts: `SphereFactRow`,
    // `SphereFactAdd`), which open it where they show
    provide() {
        return {
            factEditor: {
                form: () => this.form,
                categories: () => this.categories,
                busy: () => this.editing,
                ownFact: (id) => (this.thing?.facts || []).find((fact) => fact.fact_id === id) || null,
                edit: (fact) => this.startEdit(fact),
                add: (category, anchor) => this.startAddIn(category, anchor),
                save: () => this.saveForm(),
                cancel: () => {
                    this.form = null;
                },
                remove: (fact) => this.removeFact(fact),
            },
        };
    },
    data() {
        return {
            asOfMenu: false,
            asOfYear: null,
            asOfMonth: null,
            // the open fact form: {mode: 'add'|'edit'|'end', factId?, ...}
            form: null,
            // what follows a save once its reply is in: {factId (null: the
            // fact the reply adds), known (fact ids before), stubs to make,
            // names (re-picks) to teach}
            afterSave: null,
            // the name being edited: {text, sent}
            rename: null,
        };
    },
    computed: {
        thing() {
            return this.worlds.thing;
        },
        info() {
            return this.thing ? kindInfo(this.thing.kind) : null;
        },
        categories() {
            return this.info?.categories || [];
        },
        isHeritage() {
            return HERITAGE_KINDS.includes(this.thing?.kind);
        },
        // a kind that inherits, with something to inherit (a character
        // without heritage has none)
        showInherited() {
            return INHERITING_KINDS.includes(this.thing?.kind) && !!this.thing.inherited?.length;
        },
        // the date the page shows: its own, or the world's "now" for latest
        viewingDate() {
            return this.thing?.at || this.worlds.currentWorld?.now || null;
        },
        viewingLabel() {
            return this.thing?.at ? formatDate(this.worlds.calendar, this.thing.at) : 'latest';
        },
        monthOptions() {
            const names = this.worlds.calendar?.month_names || [];
            return names.map((title, index) => ({ title, value: index + 1 }));
        },
        proseSectionCount() {
            return Object.keys(this.thing?.prose || {}).length;
        },
        // a stub has nothing written yet to make prose from; a sphere's
        // summary (its description) heads its sphere part instead
        proseShown() {
            if (this.thing?.stub) {
                return {};
            }
            const prose = this.thing?.prose || {};
            if (this.thing?.sphere) {
                const { description: _summary, ...rest } = prose;
                return rest;
            }
            return prose;
        },
        // every kind a sphere's drawer can hold has a Part of line
        hasPartOf() {
            return PART_OF_KINDS.includes(this.thing?.kind);
        },
        // the facts listed (`listedFacts`): a sphere's statements, timeline
        // and about facts, and a character's "but…" exceptions, show (and
        // are edited) elsewhere on the page
        shownFacts() {
            return listedFacts(this.thing);
        },
        stubOfPage() {
            const thing = this.thing;
            return {
                id: thing.id,
                name: thing.name,
                kind: thing.kind,
                mentions: (thing.mentions || []).length,
                ignored: !!thing.stub?.ignored,
            };
        },
        editing() {
            return EDIT_ACTIONS.some((action) => this.worlds.pending[action]);
        },
        shownFields() {
            const calendar = this.worlds.calendar;
            const fields = [];
            for (const [name, value] of Object.entries(this.thing.fields)) {
                // a branch's parent heads its sphere part
                if (HIDDEN_FIELDS.includes(name) || value == null || (name === 'parent' && this.thing.kind === 'sphere')) {
                    continue;
                }
                const field = { name, label: FIELD_LABELS[name] || name };
                if (typeof value === 'object' && 'instant' in value) {
                    field.text = formatDate(calendar, value);
                    if (name === 'born') {
                        Object.assign(field, this.bornDetails(value));
                    }
                } else if (name === 'heritage' && typeof value === 'string') {
                    // a deleted target has no page to open: plain text
                    const links = this.worlds.heritageLinks(value);
                    if (links.length) {
                        field.links = links;
                    } else if (this.findThing(value)) {
                        field.links = [this.link(value)];
                    } else {
                        field.text = '(deleted)';
                        field.deleted = true;
                    }
                } else if (typeof value === 'string' && THING_ID.test(value)) {
                    field.links = [this.link(value)];
                } else if (Array.isArray(value) && value.length && value.every((item) => THING_ID.test(item))) {
                    field.links = value.map((id) => this.link(id));
                } else {
                    field.text = String(value);
                }
                fields.push(field);
            }
            return fields;
        },
        // the dated changes, the birth and the scenes, in date order; a
        // point is "reached" when it's on or before the viewing date
        timelinePoints() {
            const calendar = this.worlds.calendar;
            const points = [];
            const born = this.thing.fields.born;
            if (born && typeof born === 'object') {
                points.push({ date: born, text: 'born' });
            }
            for (const entry of this.thing.timeline) {
                if (!entry.date || (entry.change === 'field' && entry.field === 'name' && !entry.value)) {
                    continue;
                }
                let text;
                if (entry.change === 'fact_start') {
                    text = cut(entry.text || '');
                } else if (entry.change === 'fact_end') {
                    text = 'ends: ' + cut(entry.text || '', 22);
                } else {
                    text = entry.field;
                }
                points.push({ date: entry.date, text });
            }
            for (const scene of this.thing.appears_in) {
                points.push({ date: scene.start, text: `“${cut(scene.name, 24)}”`, scene: true });
            }
            const at = this.thing.at ? this.thing.at.instant : Infinity;
            return points
                .sort((a, b) => a.date.instant - b.date.instant)
                .map((point) => ({
                    ...point,
                    dateLabel: formatDate(calendar, point.date),
                    reached: point.date.instant <= at,
                }));
        },
    },
    watch: {
        thing(thing, before) {
            // another thing, or the reply to the form's own edit
            if (this.afterSave && this.form?.sent && thing?.id === before?.id) {
                this.afterSaved(thing);
            }
            if (!thing || thing.id !== before?.id || this.form?.sent) {
                this.form = null;
                this.afterSave = null;
            }
            if (!thing || thing.id !== before?.id || this.rename?.sent) {
                this.rename = null;
            }
        },
        editing(now) {
            // the edit failed (no reply replaced the thing): keep the form
            if (!now && this.form?.sent) {
                this.form = { ...this.form, sent: false };
                this.afterSave = null;
            }
        },
        // the rename failed (no reply replaced the thing): keep it open
        'worlds.pending.set_field'(now) {
            if (!now && this.rename?.sent) {
                this.rename = { ...this.rename, sent: false };
            }
        },
    },
    methods: {
        canPromote,
        formatDate,
        spanLabel,
        validYear(year) {
            return Number.isInteger(year) && year >= 1 && year <= 9999;
        },
        link(id) {
            return { id, name: this.thingName(id) };
        },
        // a born field's age at the viewing date and the life stage (with
        // the lifespan it's measured against, flagged when past it)
        bornDetails(born) {
            let text = formatDate(this.worlds.calendar, born);
            if (this.viewingDate) {
                text += ` · age ${ageAt(born, this.viewingDate)}`;
            }
            const stage = this.thing.life_stage;
            if (stage) {
                text += ` · ${stage.stage}`;
            }
            const lifespan = this.thing.numbers?.lifespan;
            return {
                text,
                pastLifespan: !!stage?.past_lifespan,
                note: stage && lifespan != null ? `(lifespan ~${formatNumber(lifespan)})` : null,
            };
        },
        // what an own fact overrides, as "Snowy: Yellow eyes."
        overrideNotes(fact) {
            return (fact.overrides || [])
                .map((id) => (this.thing.inherited || []).find((item) => item.fact_id === id))
                .filter(Boolean)
                .map((item) => `${item.source_name}: ${item.rendered}`);
        },
        findThing(id) {
            for (const list of Object.values(this.worlds.things)) {
                const found = list.find((thing) => thing.id === id);
                if (found) {
                    return found;
                }
            }
            return null;
        },
        thingName(id) {
            return this.findThing(id)?.name ?? id.slice(0, 8);
        },
        openAsOf() {
            const parts = this.viewingDate ? dateParts(this.viewingDate) : null;
            this.asOfYear = parts ? parts.year : null;
            this.asOfMonth = this.thing?.at && this.thing.at.precision !== 'year' ? parts.month : null;
        },
        applyAsOf() {
            if (!this.validYear(this.asOfYear)) {
                return;
            }
            this.viewAt(dateOf(this.asOfYear, this.asOfMonth || null));
        },
        viewAt(date) {
            this.asOfMenu = false;
            const at = date ? { instant: date.instant, precision: date.precision } : null;
            this.worlds.viewThingAt(at);
        },
        startRename() {
            this.rename = { text: this.thing.name, sent: false };
        },
        saveRename() {
            const name = this.rename?.text.trim();
            if (!name || this.rename.sent) {
                return;
            }
            if (name === this.thing.name) {
                this.rename = null;
                return;
            }
            this.worlds.renameThing(name);
            this.rename = { ...this.rename, sent: true };
        },
        // the words and links of `fact` (own or inherited), for its form
        // (each link remembers the thing it had: `was`)
        editState(fact) {
            const ignored = this.worlds.stubs.filter((stub) => stub.ignored).map((stub) => stub.id);
            const state = factEditState(fact.segments, fact.text || fact.rendered || '', ignored);
            return { ...state, links: state.links.map((link) => ({ ...link, was: link.ref })) };
        },
        startAdd() {
            this.form = { mode: 'add', category: this.categories[0], text: '', fromYear: null, untilYear: null, picks: {}, refs: {}, links: [], stubs: [] };
        },
        // an add form opened where a sphere shows that category (`anchor`)
        startAddIn(category, anchor) {
            this.form = { mode: 'add', category, anchor, text: '', fromYear: null, untilYear: null, picks: {}, refs: {}, links: [], stubs: [] };
        },
        startEdit(fact) {
            const { text, links } = this.editState(fact);
            this.form = {
                mode: 'edit',
                factId: fact.fact_id,
                category: fact.category,
                text,
                fromYear: yearOf(fact.valid_from),
                untilYear: yearOf(fact.valid_until),
                original: fact,
                originalText: text,
                picks: {},
                refs: {},
                links,
                stubs: [],
            };
        },
        startOverride(fact) {
            const { text, links } = this.editState(fact);
            this.form = {
                mode: 'override',
                factId: fact.fact_id,
                category: overrideCategory(this.thing.kind, fact.category),
                text,
                replaces: `${fact.source_name}'s “${fact.rendered}”`,
                picks: {},
                refs: {},
                links,
                stubs: [],
            };
        },
        startEnd(fact) {
            this.form = { mode: 'end', factId: fact.fact_id, untilYear: yearOf(this.viewingDate) };
        },
        saveForm() {
            const form = this.form;
            const year = (value) => (this.validYear(value) ? dateOf(value) : null);
            const matches = form.mode === 'end' ? [] : this.worlds.matchesFor(form.text, this.worlds.thingAt);
            // what's sent is the trimmed text: the spans count in it
            const text = form.mode === 'end' ? '' : form.text.trim();
            let links = null;
            if (form.mode !== 'end') {
                const picks = form.picks || {};
                links = factLinkPayload(text, matches, picks, form.refs || {}, form.links || []);
                // re-picks by name, and of one link
                const names = [
                    ...repicks(matches, picks),
                    ...(form.links || [])
                        .filter((link) => link.ref !== link.was && link.ref !== NEW_THING)
                        .map((link) => ({ id: link.ref, name: link.text })),
                ].filter((repick) => repick.id !== this.thing.id);
                this.afterSave = form.stubs?.length || names.length
                    ? {
                        factId: form.mode === 'edit' ? form.factId : null,
                        known: this.thing.facts.map((fact) => fact.fact_id),
                        stubs: form.stubs || [],
                        names,
                    }
                    : null;
            }
            if (form.mode === 'add') {
                this.worlds.addFact(form.category, text, year(form.fromYear), year(form.untilYear), links);
            } else if (form.mode === 'override') {
                this.worlds.overrideFact(form.factId, form.category, text, links);
            } else if (form.mode === 'end') {
                this.worlds.endFact(form.factId, dateOf(form.untilYear));
            } else {
                const original = form.original;
                const changes = {};
                // the words, or what they link to, changed
                const relinked = Object.keys(form.picks).length > 0
                    || Object.keys(form.refs).length > 0
                    || form.links.some((link) => link.ref !== link.was);
                if (text !== form.originalText || relinked) {
                    changes.text = text;
                }
                if (form.category !== original.category) {
                    changes.category = form.category;
                }
                // a year left as it was keeps the stored date (and its precision)
                const sameYear = (date, value) => yearOf(date) === (this.validYear(value) ? value : null);
                if (!sameYear(original.valid_from, form.fromYear)) {
                    changes.valid_from = year(form.fromYear);
                }
                if (!sameYear(original.valid_until, form.untilYear)) {
                    changes.valid_until = year(form.untilYear);
                }
                if (!Object.keys(changes).length) {
                    // only stubs to make, if any: the fact is as it was
                    if (this.afterSave) {
                        this.afterSaved(this.thing);
                    }
                    this.form = null;
                    return;
                }
                this.worlds.correctFact(form.factId, changes, 'text' in changes ? links : {});
            }
            this.form = { ...form, sent: true };
        },
        // what follows a save (`afterSave`), now that `thing` holds it:
        // the re-picked things learn their names, and the stubs are made in
        // the fact edited, or the one the reply added
        afterSaved(thing) {
            const pending = this.afterSave;
            this.afterSave = null;
            for (const repick of pending.names) {
                this.worlds.addOtherName(repick.id, repick.name);
            }
            const fact = pending.factId
                ? thing.facts.find((f) => f.fact_id === pending.factId)
                : thing.facts.find((f) => !pending.known.includes(f.fact_id));
            if (!fact) {
                return;
            }
            for (const stub of pending.stubs) {
                if ((fact.rendered || '').includes(stub.text)) {
                    this.worlds.makeStub(fact.fact_id, stub.text, stub.kind);
                }
            }
        },
        // `segments[index]` of the own fact `fact` now links `to`, its
        // words kept
        repointLink(fact, { index, to }) {
            const occurrence = refOccurrence(fact.text, fact.segments, index);
            if (occurrence !== null && to !== fact.segments[index].ref) {
                this.worlds.repointRef(fact.fact_id, occurrence, to);
            }
        },
        removeFact(fact) {
            this.worlds.removeFact(fact.fact_id);
            this.form = { ...this.form, sent: true };
        },
    },
};
</script>

<style scoped>
.thing-name {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}

.rename-input {
    min-width: 260px;
}

.world-date {
    color: rgb(var(--v-theme-date));
}

.point-date {
    font-family: monospace;
    font-size: 11px;
    margin-right: 6px;
}

.point-text {
    font-size: 12px;
}

.field {
    margin: 4px 0;
}

.field-label {
    min-width: 80px;
    font-weight: 600;
    color: rgb(var(--v-theme-muted));
}

.override-note {
    margin-left: 6px;
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
}

.thing-link {
    color: rgb(var(--v-theme-link));
    text-decoration: underline dotted;
}

.fact {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 2px 0;
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
    min-width: 80px;
    text-align: right;
}

.stub-panel {
    border: 1px dashed rgb(var(--v-theme-foreign));
    border-radius: 6px;
}

.prose {
    background: rgb(var(--v-theme-raised));
    border-radius: 6px;
    line-height: 1.5;
    white-space: pre-wrap;
}
</style>
