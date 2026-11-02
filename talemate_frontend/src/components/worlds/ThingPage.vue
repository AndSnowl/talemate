<template>
    <div class="thing-page" :data-testid="draft ? 'draft-page' : 'thing-page'">
        <!-- a draft: its bar, and what it could be instead -->
        <template v-if="draft && thing">
            <DraftBar :draft="worlds.draft" :counts="countsText" :can-accept="!!edited.name.trim()" :locked="draftLocked" :matching-stub="matchingStub" @accept="acceptDraft()" @fill-stub="acceptDraft(matchingStub.id)" />
            <v-alert v-if="worlds.previewError" type="error" variant="tonal" density="compact" class="mb-2">{{ worlds.previewError }}</v-alert>
        </template>

        <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <v-btn v-if="!draft" variant="text" size="small" prepend-icon="mdi-arrow-left" data-testid="thing-back" @click="worlds.goBack()">Back</v-btn>
            <template v-if="thing">
                <v-text-field
                    v-if="draft"
                    :model-value="edited.name"
                    label="Name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="draft-name"
                    data-testid="draft-name"
                    @update:model-value="edit({ name: $event })"
                ></v-text-field>
                <div v-else-if="rename" class="d-flex align-center ga-2" data-testid="rename-field">
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
                    <!-- Name it… (languages 4a revised): rename from a language -->
                    <v-btn v-if="!draft && thing.kind !== 'language'" variant="text" size="x-small" color="accent" prepend-icon="mdi-rename" data-testid="name-it-thing" @click="nameItThing">Name it…</v-btn>
                </template>
                <!-- a draft's kind can change (its facts' categories follow) -->
                <v-select
                    v-if="draft"
                    :model-value="edited.kind"
                    :items="kindItems"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="draft-kind"
                    data-testid="draft-kind"
                    aria-label="Kind"
                    @update:model-value="setDraftKind"
                ></v-select>
                <v-chip v-else size="x-small" label variant="tonal" color="muted" :prepend-icon="info?.icon" data-testid="thing-kind">{{ thing.kind }}</v-chip>
                <TagChip v-if="draft" :tag="edited.tag" local @pick="edit({ tag: $event })" />
                <TagChip v-else :thing-id="thing.id" :tag="thing.tag" />
                <!-- the draft's own name flagged (final review 6): its
                     facts show it as the entry itself, unmarked -->
                <div v-if="draft && nameFlag" class="w-100 d-flex align-center flex-wrap ga-2 text-body-2 name-flag-row" data-testid="draft-name-flag">
                    <span class="name-flagged">{{ nameFlag.name }}</span>
                    <span class="text-muted">flagged: {{ nameFlag.why }}</span>
                    <v-btn size="x-small" variant="outlined" color="accent" prepend-icon="mdi-rename" data-testid="draft-name-flag-name-it" @click="nameItOwnName">Name it…</v-btn>
                    <v-btn size="x-small" variant="text" data-testid="draft-name-flag-keep" @click="worlds.markAction(nameFlag.id, 'keep')">Keep it</v-btn>
                </div>
                <span v-if="everydayName" class="text-caption text-muted" data-testid="thing-everyday">usually called “{{ everydayName }}”</span>
                <!-- its other names (edited under Other names) -->
                <span v-if="otherNames.length" class="d-inline-flex align-center flex-wrap ga-1" data-testid="thing-other-names">
                    <span class="text-caption text-muted">also</span>
                    <v-chip
                        v-for="other in otherNames"
                        :key="other.index"
                        size="x-small"
                        label
                        variant="outlined"
                        data-testid="thing-other-name"
                    >{{ other.name }}<span v-if="otherNameLanguage(other.index)" class="text-muted ml-1">· {{ otherNameLanguage(other.index) }}</span></v-chip>
                </span>
                <span v-if="thing.hint" class="text-caption text-muted" data-testid="thing-hint">· written with the prompt hint <b>{{ thing.hint }}</b></span>
                <v-spacer></v-spacer>

                <template v-if="!draft">
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

                    <!-- a language's page: ask for a change in plain words -->
                    <v-btn
                        v-if="isLanguage"
                        variant="outlined"
                        size="small"
                        prepend-icon="mdi-auto-fix"
                        data-testid="language-change-open"
                        @click="worlds.openLanguageChange({ targetId: thing.id })"
                    >Change it…</v-btn>

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
                        v-if="!thing.stub"
                        variant="outlined"
                        size="small"
                        prepend-icon="mdi-call-merge"
                        data-testid="merge-into"
                        @click="merging = true"
                    >Merge into…</v-btn>

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
            </template>
        </div>

        <div v-if="!thing" class="d-flex justify-center pa-8">
            <v-progress-circular indeterminate color="accent"></v-progress-circular>
        </div>

        <template v-else>
            <!-- a draft with candidates: the same thing as one of them?
                 (about its name, so right under it) -->
            <SameThingAsk
                v-if="draft && !edited.stub_id && edited.same_as && edited.same_as.length"
                class="mb-3"
                :name="edited.name"
                :kind="edited.kind"
                :offers="edited.same_as"
                :verdict="edited.verdict"
                :chosen="edited._same || null"
                :exclude="ownIds"
                @choose="edit({ _same: $event })"
            />

            <template v-if="!draft">
                <v-alert
                    v-if="worlds.stubRepointed && worlds.stubRepointed.target.id === thing.id"
                    type="success"
                    variant="tonal"
                    density="compact"
                    class="mb-3"
                    closable
                    data-testid="stub-repointed"
                    @click:close="worlds.clearStubRepointed()"
                >
                    {{ repointedNote(worlds.stubRepointed) }}
                </v-alert>
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
            </template>

            <!-- Change it… (languages 3b-2b): under the header, across the tabs -->
            <LanguageChange v-if="changeHere" class="mt-3" :thing="thing" />

            <!-- a language's page (languages 3a): About is the entry's own
                 page (facts, connections, timeline); the others are the
                 language's parts, as the old culture page showed them -->
            <v-tabs
                v-if="isLanguage"
                v-model="languageTab"
                density="compact"
                color="primary"
                class="mt-2 language-tabs"
                data-testid="language-tabs"
            >
                <v-tab v-for="tab in LANGUAGE_TABS" :key="tab.value" :value="tab.value" :data-testid="'language-tab-' + tab.value">{{ tab.title }}</v-tab>
            </v-tabs>
            <!-- the Language tab, in chapters; the Lexicon -->
            <LanguageBook v-if="isLanguage && languageTab === 'language'" class="mt-3" :thing="thing" @fill-names="worlds.openLanguageChange({ targetId: thing.id, names: true })" />
            <LanguageSections v-else-if="isLanguage && languageTab === 'lexicon'" class="mt-3" :thing="thing" tab="lexicon" />

            <div v-show="!isLanguage || languageTab === 'about'">
            <!-- 3. Facts, beside the prose -->
            <v-row class="mt-1">
                <v-col cols="12" md="6">
                    <!-- the entry's summary fact heads the left column (polish 3) -->
                    <div v-if="summaryFact" class="summary" data-testid="entry-summary">
                        <FactRow
                            :fact="factView(summaryFact)"
                            :exclude="[thing.id]"
                            text-class="summary-text"
                            @repoint="repointLink(summaryFact, $event)"
                            @select="selected(summaryFact, $event)"
                            @edit="startEdit(summaryFact)"
                            @dates="startEdit(summaryFact, 'dates')"
                            @end="startEnd(summaryFact)"
                            @remove="worlds.removeFact(summaryFact.fact_id)"
                        >
                            <div v-if="form && form.factId === summaryFact.fact_id" class="my-2">
                                <ThingFactForm :form="form" :categories="categories" :busy="editing" @save="saveForm" @cancel="form = null" @remove="removeFact(summaryFact)" />
                            </div>
                        </FactRow>
                    </div>
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
                    <template v-if="!draft">
                        <div v-if="thing.kind === 'being'" class="field d-flex align-center flex-wrap ga-2" data-testid="being-existence">
                            <span class="field-label">Exists</span>
                            <v-btn-toggle
                                :model-value="existence"
                                density="compact"
                                variant="outlined"
                                divided
                                mandatory
                                color="accent"
                                :disabled="!!worlds.pending.set_field"
                                @update:model-value="setExistence"
                            >
                                <v-btn v-for="value in existenceValues" :key="value" :value="value" size="small">{{ value }}</v-btn>
                            </v-btn-toggle>
                            <span class="text-caption text-muted">{{ existenceNote }}</span>
                        </div>
                    </template>
                    <!-- a page's or a draft's: the page writes, a draft keeps -->
                    <ThingNumbers
                        v-if="isHeritage"
                        :key="'numbers-' + editorKey"
                        :fields="numberFields"
                        :numbers="thing.numbers"
                        :busy="editorBusy"
                        @set="setNumber"
                    />
                    <ThingAka
                        :key="'aka-' + editorKey"
                        :aka="akaList"
                        :main-name="thing.name"
                        :busy="editorBusy"
                        :thing-id="draft ? null : thing.id"
                        @save="saveAka"
                    />

                    <!-- In, a section of its own just above Facts (a draft's
                         rows kept in the draft) -->
                    <EntryIn
                        :thing="thing"
                        :draft="draft"
                        @add="addDraftFiling"
                        @change="(key, change) => edit(changeFiling(edited, key, draftFiling(change)))"
                        @show-under="(key, tag) => edit(setFilingShowUnder(edited, key, tag))"
                        @remove="edit(removeFiling(edited, $event))"
                    />

                    <!-- who speaks what here (languages 3a); a language's
                         own page has none -->
                    <EntryLanguages v-if="!draft && thing.kind !== 'language'" :thing="thing" />
                    <!-- a draft's, found from the owner's words (languages
                         4a); none in a world without languages -->
                    <EntryLanguages
                        v-else-if="draft && thing.kind !== 'language'"
                        :thing="thing"
                        draft
                        :rows="edited?.languages || []"
                        :inherited-rows="edited?.inherited_languages || []"
                        @change="worlds.draftLanguages($event)"
                    />

                    <!-- "+ Add facts…"'s form and draft wrap onto their own
                         line under the heading (a draft page's nested draft
                         indented) -->
                    <div class="d-flex align-center flex-wrap mt-4 mb-1" data-testid="facts-heading">
                        <span class="text-overline text-muted">{{ showInherited ? 'Own facts' : 'Facts' }}</span>
                        <span v-if="draft" class="text-caption text-muted ml-2">{{ tickedCount }} ticked</span>
                        <v-spacer></v-spacer>
                        <EntryAddFacts v-if="draft || !thing.stub" :thing="thing" :on-draft="draft" />
                        <v-btn
                            v-if="!form || form.factId || form.index != null"
                            variant="text"
                            size="small"
                            color="accent"
                            prepend-icon="mdi-plus"
                            :disabled="factFormOpen"
                            :title="factFormOpen ? 'save or cancel the edit first' : null"
                            @click="startAdd"
                        >Add fact</v-btn>
                        <!-- a language reworked to fit this entry (languages 3b-2b) -->
                        <v-btn
                            v-if="!isLanguage"
                            variant="text"
                            size="small"
                            color="accent"
                            prepend-icon="mdi-auto-fix"
                            data-testid="entry-change-language"
                            @click="worlds.openLanguageChange({ originId: thing.id })"
                        >Change a language to fit this…</v-btn>
                    </div>

                    <div v-if="form && !form.factId && form.index == null" class="mb-2">
                        <ThingFactForm :form="form" :categories="categories" :busy="editing" @save="saveForm" @cancel="form = null" />
                    </div>

                    <template v-if="draft">
                        <!-- a stub's facts so far, written already -->
                        <div v-for="fact in thing.facts" :key="fact.fact_id" class="stub-fact text-muted" data-testid="draft-stub-fact">
                            <LinkedText :segments="fact.segments" :text="fact.rendered" />
                            <span class="text-caption"> · on the stub already</span>
                        </div>
                        <div v-if="!draftRows.length" class="text-body-2 text-muted">No facts in this draft.</div>
                        <FactRow
                            v-for="row in draftRows"
                            :key="'d' + row.index"
                            :fact="row.view"
                            draft
                            :exclude="ownIds"
                            @tick="edit(tickFact(edited, row.index, $event))"
                            @select="selectedDraft(row, $event)"
                            @edit="startDraftForm(row, 'edit')"
                            @dates="startDraftForm(row, 'dates')"
                            @end="startDraftForm(row, 'end')"
                            @remove="edit(removeDraftFact(edited, row.index))"
                            @move="edit(moveFactTo(edited, row.index, $event))"
                            @copy="edit(copyFactTo(edited, row.index, $event))"
                            @held="edit(holdFact(edited, row.index, $event))"
                        >
                            <template v-if="row.fact.repeat_of" #match>
                                <PreviewRepeats
                                    :repeat="row.fact.repeat_of"
                                    :choice="repeatChoice(row.fact)"
                                    @settle="edit(settleRepeat(edited, row.index, $event))"
                                />
                            </template>
                            <div v-if="form && form.draft && form.index === row.index" class="my-2">
                                <ThingFactForm :form="form" :categories="categories" :removable="false" @save="saveForm" @cancel="form = null" />
                            </div>
                        </FactRow>

                        <!-- what it inherits, each ticked as kept: unticking one
                             the model missed marks it replaced by one of its own.
                             Each on the saved page's inherited line (`InheritedLine`) -->
                        <template v-if="edited.inherited && edited.inherited.length">
                            <div class="suggestion-heading mt-3">Inherited (untick to replace)</div>
                            <SuggestionRow
                                v-for="row in edited.inherited"
                                :key="row.fact_id"
                                fill
                                :ticked="overriderOf(row) < 0"
                                :dropped="false"
                                tick-label="Kept"
                                :disabled="!edited.facts.length"
                                testid="preview-inherited"
                                @tick="setKept(row, $event)"
                            >
                                <InheritedLine :fact="inheritedLine(row)" actions="none" :overridden="overriderOf(row) >= 0" />
                                <template v-if="overriderOf(row) >= 0" #under>
                                    <v-select
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
                                </template>
                            </SuggestionRow>
                        </template>
                    </template>

                    <template v-else>
                        <div v-if="!shownFacts.length" class="text-body-2 text-muted">No facts true at this date.</div>
                        <FactRow
                            v-for="fact in shownFacts"
                            :key="fact.fact_id"
                            :fact="factView(fact)"
                            :exclude="[thing.id]"
                            @repoint="repointLink(fact, $event)"
                            @select="selected(fact, $event)"
                            @edit="startEdit(fact)"
                            @dates="startEdit(fact, 'dates')"
                            @end="startEnd(fact)"
                            @remove="worlds.removeFact(fact.fact_id)"
                        >
                            <template #notes>
                                <span v-for="note in overrideNotes(fact)" :key="note" class="override-note">(overrides {{ note }})</span>
                            </template>
                            <div v-if="form && form.factId === fact.fact_id" class="my-2">
                                <ThingFactForm :form="form" :categories="categories" :busy="editing" @save="saveForm" @cancel="form = null" @remove="removeFact(fact)" />
                            </div>
                        </FactRow>

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
                        <!-- up to and including the section being created
                             (or all of them, idle): what follows moves
                             below the draft instead, so nothing but the
                             section being created sits next to it -->
                        <HeritageSections
                            v-if="thing.kind === 'species'"
                            :species-id="thing.id"
                            :races="thing.races"
                            :mixes="thing.mixes"
                            :creating="heritageCreating"
                            :until="heritageCreating"
                            @create="heritageCreating = $event"
                        />
                        <!-- while a race/mix is drafted below the row, Stubs
                             this entry named moves there too, right after
                             it: otherwise it sits between Races/Mixes and
                             the draft, reading as if the draft belonged to
                             it instead -->
                        <NamedStubs v-if="!heritageTailBelow" :stubs="thing.named_stubs || []" />
                    </template>
                </v-col>

                <v-col cols="12" md="6">
                    <div v-if="thing.stub && !draft" data-testid="stub-mentions-list">
                        <div class="text-overline text-muted">Mentioned in</div>
                        <div v-if="!thing.mentions.length" class="text-body-2 text-muted">Nothing mentions it now.</div>
                        <div v-for="mention in thing.mentions" :key="mention.fact_id" class="fact" data-testid="stub-mention">
                            <a class="thing-link" href="#" @click.prevent="worlds.openThing(mention.owner_id)">{{ mention.owner_name }}</a>
                            <span class="text-caption text-muted"> ({{ mention.category }})</span>:
                            {{ mention.text }}
                        </div>
                    </div>
                    <div v-for="(prose, section) in proseShown" :key="section" class="mb-3" :data-testid="draft ? 'draft-prose' : null">
                        <div class="d-flex align-center ga-2">
                            <span class="text-overline text-muted">{{ section }} (generated)</span>
                            <v-chip v-if="prose.stale" size="x-small" label variant="tonal" color="warning">out of date</v-chip>
                            <v-spacer></v-spacer>
                            <v-btn
                                v-if="!draft && proseSectionCount > 1"
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

                    <template v-if="!draft">
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
                    </template>

                    <!-- what's filed in it and what names it, under Appears
                         in (polish 3): a stub's draft shows the stub's, as
                         they are -->
                    <template v-if="!draft || thing.id">
                        <EntryConnected :thing="thing" :readonly="draft" class="mt-4" />
                        <EntryMentionedIn :thing="thing" />
                    </template>
                </v-col>
            </v-row>

            <!-- a race or mix draft (opened by Races'/Mixes' "+ New
                 race"/"+ New mix", in the left column above), below the
                 two columns at the entry's full width, so it gets the same
                 width and two-column layout as any entry page -->
            <CreateBox
                v-if="!draft && thing.kind === 'species' && heritageCreating"
                class="mt-4"
                :kind="heritageCreating"
                :preset="heritagePreset"
                cancellable
                @cancel="heritageCreating = null"
            />
            <!-- whatever came after the section being created (Mixes,
                 drafting a race; nothing, drafting a mix) and Named
                 stubs, moved below the draft: a second row, its own
                 left column the same width as the main row's, so "+ New
                 mix" stays by its heading instead of the full width -->
            <v-row v-if="heritageTailBelow" class="mt-4">
                <v-col cols="12" md="6">
                    <HeritageSections
                        :species-id="thing.id"
                        :races="thing.races"
                        :mixes="thing.mixes"
                        :creating="heritageCreating"
                        :from="heritageCreating"
                        @create="heritageCreating = $event"
                    />
                    <NamedStubs :stubs="thing.named_stubs || []" />
                </v-col>
            </v-row>

            <template v-if="draft">
                <!-- 4. For other pages -->
                <PreviewElsewhere
                    :rows="edited.elsewhere || []"
                    type="create"
                    :new-names="edited.new_names || []"
                    :rendered="(worlds.draft.rendered || worlds.draft.page).elsewhere || []"
                    :also-here="ownTexts"
                    :exclude="ownIds"
                    @update="edit({ elsewhere: $event })"
                    @retarget="(index, target) => edit(retarget(edited, index, target))"
                    @also="edit(alsoHere(edited, $event))"
                />
                <!-- 5. Could move here -->
                <MoveHere :draft="edited" @tick="tickMove" />
                <!-- 6. New stubs -->
                <PreviewStubs :rows="edited.new_names || []" :marks="edited.marks || []" @change="(name, change) => edit(changeNewName(edited, name, change))" />
                <!-- 7. File into this -->
                <div v-if="(edited.file_into || []).length" class="mt-3" data-testid="draft-file-into">
                    <div class="suggestion-heading">File into this <span class="text-muted">· entries that look like they belong in it</span></div>
                    <SuggestionRow
                        v-for="row in edited.file_into"
                        :key="row.thing_id"
                        :ticked="!!row.ticked"
                        :tick-label="'File ' + row.name + ' into this'"
                        testid="file-into-row"
                        @tick="edit(tickFileInto(edited, row.thing_id, $event))"
                    >
                        <span class="file-into-name">{{ row.name }}</span>
                        <span v-if="row.role" class="role ml-2">{{ row.role }}</span>
                    </SuggestionRow>
                </div>
                <!-- Accept again at the foot of the draft's lists -->
                <SuggestionBar
                    foot
                    class="mt-3"
                    :busy="draftBusy"
                    :locked="draftLocked"
                    primary-label="Accept"
                    :can-primary="!!edited.name.trim()"
                    :primary-loading="!!worlds.draft.accepting"
                    testid="draft-foot"
                    :testids="{ primary: 'draft-accept-foot', discard: 'draft-discard-foot' }"
                    @discard="worlds.discardPreview()"
                    @primary="acceptDraft()"
                >
                    <template v-if="matchingStub" #primary-extra>
                        <FillStubButton
                            :name="matchingStub.name"
                            :loading="!!worlds.draft.accepting"
                            :disabled="draftBusy || !edited.name.trim() || !!draftLocked"
                            :title="draftLocked"
                            testid="fill-stub-instead-foot"
                            @fill="acceptDraft(matchingStub.id)"
                        />
                    </template>
                </SuggestionBar>
            </template>

            <EntryTimeline :lines="thing.entry_timeline || []" class="mt-4">
                <template #actions>
                    <EntryAddFacts v-if="draft || !thing.stub" :thing="thing" event :on-draft="draft" />
                </template>
            </EntryTimeline>
            </div>
        </template>

        <SelectionMenu
            v-model="selecting"
            :target="selection?.target"
            :words="selection?.words || ''"
            :before="selection?.before || ''"
            :draft="draft"
            :blocked="selection?.blocked || ''"
            :link="selection?.link || null"
            :exclude="thing && thing.id ? [thing.id] : []"
            @stub="makeStub(false, $event)"
            @expand="makeStub(true, $event)"
            @link="linkWords"
        />
        <template v-if="!draft">
            <ThingDeleteDialog />
            <MergeDialog v-if="thing" v-model="merging" :thing="thing" />
        </template>
    </div>
</template>

<script>
import { countsLine, dateIn, defaultOverrideIndex, listedFacts, moveInEdit, previewCounts, repointedNote, useWorldsStore } from '@/stores/worlds.js';
import { ageAt, dateOf, dateParts, formatDate, spanLabel } from './worldDates.js';
import { EXISTENCE, HERITAGE_KINDS, INHERITING_KINDS, STUB_KINDS, existenceOf, kindInfo, overrideCategory } from './worldKinds.js';
import { headerNames } from './entryPage.js';
import { formatNumber } from './worldNumbers.js';
import { NEW_THING, factEditState, factLinkPayload, linkPayload, refOccurrence, repicks } from './nameHighlights.js';
import {
    addDraftFact,
    addFiling,
    alsoHere,
    changeFiling,
    changeKind,
    changeNewName,
    copyFactTo,
    draftFactRows,
    editFact,
    filingKey,
    holdFact,
    linkAt,
    moveFactTo,
    removeFact as removeDraftFact,
    removeFiling,
    repeatChoice,
    retarget,
    setDraftAka,
    setDraftNumber,
    setFilingShowUnder,
    settleRepeat,
    tickFact,
    tickFileInto,
    tickMoveHere,
} from './draftPage.js';
import CreateBox from './CreateBox.vue';
import EntryLanguages from './EntryLanguages.vue';
import LanguageBook from './LanguageBook.vue';
import LanguageChange from './LanguageChange.vue';
import LanguageSections from './LanguageSections.vue';
import DraftBar from './DraftBar.vue';
import FillStubButton from './FillStubButton.vue';
import EntryAddFacts from './EntryAddFacts.vue';
import EntryConnected from './EntryConnected.vue';
import EntryIn from './EntryIn.vue';
import EntryMentionedIn from './EntryMentionedIn.vue';
import EntryTimeline from './EntryTimeline.vue';
import FactRow from './FactRow.vue';
import HeritageSections from './HeritageSections.vue';
import InheritedLine from './InheritedLine.vue';
import LinkedText from './LinkedText.vue';
import MergeDialog from './MergeDialog.vue';
import MoveHere from './MoveHere.vue';
import NamedStubs from './NamedStubs.vue';
import PreviewElsewhere from './PreviewElsewhere.vue';
import PreviewRepeats from './PreviewRepeats.vue';
import PreviewStubs from './PreviewStubs.vue';
import SameThingAsk from './SameThingAsk.vue';
import SelectionMenu from './SelectionMenu.vue';
import StubCard from './StubCard.vue';
import SuggestionBar from './SuggestionBar.vue';
import SuggestionRow from './SuggestionRow.vue';
import TagChip from './TagChip.vue';
import ThingAka from './ThingAka.vue';
import ThingDeleteDialog from './ThingDeleteDialog.vue';
import ThingFactForm from './ThingFactForm.vue';
import ThingInherited from './ThingInherited.vue';
import ThingNumbers from './ThingNumbers.vue';
import ThingReferencedIn from './ThingReferencedIn.vue';

// fields shown elsewhere (the name; a heritage kind's numbers; the tag,
// prompt hint and filings in the header and "In"; a being's existence),
// or not for reading (voice, colour, the agent flag, other names)
const HIDDEN_FIELDS = [
    'name', 'voice', 'color', 'lifespan', 'adult_age', 'measures',
    'agent', 'existence', 'tag', 'hint', 'filings', 'aka',
    // languages 3a: who speaks what, and a language's own sections
    'languages', 'depth', 'flavour', 'sound', 'rules', 'words', 'phrases',
    'descends_from', 'similar',
];

// a language page's tabs (languages 3a): About first, the default
const LANGUAGE_TABS = [
    { value: 'about', title: 'About' },
    { value: 'language', title: 'Language' },
    { value: 'lexicon', title: 'Lexicon' },
];

// what a being's existence means for it
const EXISTENCE_NOTES = {
    real: 'It acts in the world like a character: it can be cast in scenes, and counts as a person where it is filed.',
    believed: 'Only ever spoken of in scenes.',
    undecided: 'Treated as believed until you decide.',
};

const FIELD_LABELS = {
    born: 'Born',
    kind: 'Kind',
    owner: 'Owner',
    place: 'Place',
    when: 'When',
    until: 'Until',
    heritage: 'Heritage',
    species: 'Species',
    parents: 'Parents',
    origin: 'Origin',
};

// what a draft without own fields, or a thing without other names, passes
// (one each: a new one every time would read as a change)
const NO_FIELDS = Object.freeze({});
const NO_AKA = Object.freeze([]);

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
// The entry page (mockup v3, screens A, B and D): under the header (name,
// kind, the tag chip with its picker, its everyday name, the prompt hint
// it was written with) come its summary fact, then beside its prose its
// "In" rows (`EntryIn`, a section just above Facts in the left column)
// and its facts ("+ Add facts…", `EntryAddFacts`), then what's filed in it
// grouped by tag (`EntryConnected`), what names it ("Mentioned in",
// folded) and its Timeline ("Events ▾", "+ Add event…").
//
// Curation: every page has a Timeline (`EntryTimeline`, its
// `entry_timeline`); each fact is a `FactRow`: its menu on "⋯" or a
// right-click (`FactRowActions`: Move to…, Copy to…, Held by…, Edit,
// Change dates (a dates-only form), End this, Remove), a held one tagged
// "held by X", and right-clicking words selected in it opens the
// selection menu (`SelectionMenu`: Make a stub, Make a stub and expand
// now, Link to an entry…; `make_stub_from_text`, `link_text`, the words'
// UTF-16 offsets in its rendered text). "Merge into…" opens the merge
// dialog (`MergeDialog`). A

// being has its existence picked here (real, believed or undecided); only
// a real one is a person, with "within" and "but…" on its "In" rows.
//
// The draft mode (`draft`; spec "The draft page", ruling F25: one page
// for drafts and entries): a new or expanded entry, before it's accepted,
// is this page with `thing` the draft's page (`worlds.draft.page`, the
// owner's name, kind, tag and "In" rows over it), shown by the create box
// in its place. The same header (the name and kind editable, the tag chip
// local), the same "In" (`EntryIn` in its draft mode), fact rows
// (`FactRow`), fact form (`ThingFactForm`), menus, Connected and
// Mentioned in (read-only: a stub's draft shows the stub's) and
// Timeline; every change goes to the draft (`worlds.editDraft` and
// draftPage.js), nothing is written before Accept. It adds the draft bar
// (`DraftBar`) and, in the spec's order around the shared sections,
// "Same thing?" right under the name (it's about the name), the
// repeats' "Move existing here" on its facts
// (`PreviewRepeats`) and what it inherits, then For other pages
// (`PreviewElsewhere`), Could move here (`MoveHere`), New stubs
// (`PreviewStubs`) and File into this, with Accept and Discard again at
// their foot. While a nested "+ Add facts" draft is out or held
// (`draftLocked`), every way to accept it waits, "Fill the stub …
// instead" too. A heritage draft's numbers and its other names are the
// page's editors (`ThingNumbers`, `ThingAka`), kept in the draft
// (`setDraftNumber`, `setDraftAka`); the header lists its other names
// read-only, as the page's does. What the page alone has (the as-of
// date, the timeline strip, prose regeneration, merge and delete) is
// left out.
export default {
    name: 'ThingPage',
    components: {
        CreateBox,
        EntryLanguages,
        LanguageBook,
        LanguageChange,
        LanguageSections,
        DraftBar,
        FillStubButton,
        EntryAddFacts,
        EntryConnected,
        EntryIn,
        EntryMentionedIn,
        EntryTimeline,
        FactRow,
        HeritageSections,
        InheritedLine,
        LinkedText,
        MergeDialog,
        MoveHere,
        NamedStubs,
        PreviewElsewhere,
        PreviewRepeats,
        PreviewStubs,
        SameThingAsk,
        SuggestionBar,
        SuggestionRow,
        SelectionMenu,
        StubCard,
        ThingAka,
        ThingDeleteDialog,
        ThingFactForm,
        ThingInherited,
        ThingNumbers,
        ThingReferencedIn,
        TagChip,
    },
    props: {
        // the draft mode: the open draft (`worlds.draft`) as the page it
        // will be; `stay` (a nested mix box) accepts without opening it
        draft: { type: Boolean, default: false },
        stay: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            LANGUAGE_TABS,
            // a language page's open tab (languages 3a)
            languageTab: 'about',
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
            // the merge dialog is open
            merging: false,
            // selected words of a fact (`{factId, start, end, words,
            // target}`) and whether their menu is open
            selection: null,
            selecting: false,
            existenceValues: EXISTENCE,
            // a species page's Races/Mixes: the kind its create box (below
            // the two columns) is showing, if any
            heritageCreating: null,
        };
    },
    computed: {
        // a mark on the draft's own name (final review 6)
        nameFlag() {
            const name = (this.edited?.name || '').toLowerCase();
            return (this.edited?.marks || []).find((m) => m.name && name.includes(m.name.toLowerCase())) || null;
        },
        // the Change it… panel belongs on this page: its language's, or
        // the entry it was asked from
        changeHere() {
            const change = this.worlds.languageChange;
            if (!change) return false;
            return change.originId ? change.originId === this.thing.id : this.isLanguage && change.targetId === this.thing.id;
        },
        thing() {
            return this.draft ? this.draftThing : this.worlds.thing;
        },
        // the draft's preview as the owner left it
        edited() {
            return this.worlds.draft?.edited || null;
        },
        // the draft as the page it will be: the server's page of it
        // (a stub's draft starts from the stub's own page), with the
        // owner's name, kind, tag and "In" rows, and its prose; its
        // timeline and prose linked as the server rendered the owner's
        // copy (`draft.rendered`, P6), once it has
        draftThing() {
            const draft = this.worlds.draft;
            if (!draft) {
                return null;
            }
            const page = draft.page;
            const edited = draft.edited;
            const kept = (page.in || []).filter((row) => !row.draft);
            const keptIds = new Set(kept.map((row) => row.target_id));
            const own = (edited.filings || [])
                .filter((row) => !row.target_id || !keptIds.has(row.target_id))
                .map((row) => ({
                    ...row,
                    until: null,
                    within_id: row.within || null,
                    within_name: row.within ? this.thingName(row.within) : null,
                    exceptions: [],
                    draft: true,
                }));
            return {
                ...page,
                name: edited.name,
                kind: edited.kind,
                tag: edited.tag,
                hint: edited.hint,
                aka: edited.aka || NO_AKA,
                numbers: draft.rendered?.numbers || page.numbers,
                in: [...kept, ...own],
                facts: (page.facts || []).filter((fact) => !fact.draft),
                inherited: [],
                prose: Object.fromEntries(Object.entries(edited.prose || {}).map(([section, text]) => [section, { text, stale: false }])),
                prose_segments: draft.rendered?.prose_segments || page.prose_segments,
                entry_timeline: draft.rendered?.entry_timeline || page.entry_timeline,
            };
        },
        kindItems() {
            const kinds = STUB_KINDS.includes(this.edited?.kind) ? STUB_KINDS : [...STUB_KINDS, this.edited?.kind].filter(Boolean);
            return kinds.map((kind) => ({ title: kindInfo(kind)?.singular || kind, value: kind }));
        },
        // the stub a draft expands: never a target of its own
        ownIds() {
            return this.edited?.stub_id ? [this.edited.stub_id] : [];
        },
        // a draft's own facts (`draftFactRows`), each with the row
        // FactRow shows
        draftRows() {
            if (!this.draft || !this.worlds.draft) {
                return [];
            }
            return draftFactRows(this.worlds.draft.page, this.edited, this.worlds.draft.rendered).map((row) => ({
                ...row,
                view: {
                    text: row.fact.text,
                    segments: row.segments,
                    category: row.fact.category,
                    valid_from: row.fact.since || null,
                    valid_until: row.fact.until || null,
                    held_by: row.fact.held_by ? { id: row.fact.held_by, name: row.fact.held_by_name } : null,
                    ticked: row.fact.ticked,
                    local: row.local,
                },
            }));
        },
        ownTexts() {
            return this.draftRows.map((row) => row.fact.text);
        },
        tickedCount() {
            return this.draftRows.filter((row) => row.fact.ticked !== false).length;
        },
        ownFactItems() {
            return (this.edited?.facts || []).flatMap((fact, index) => (fact.removed ? [] : [{ title: fact.text, value: index }]));
        },
        // the stub of this kind the draft is named like (not one it expands)
        matchingStub() {
            const id = this.edited?.matching_stub_id;
            if (!id || this.edited.stub_id) {
                return null;
            }
            return { id, name: this.worlds.stubInfo(id)?.name || this.edited.name };
        },
        countsText() {
            const same = this.edited?._same;
            const onto = same
                ? (this.edited.same_as || []).find((offer) => offer.thing_id === same)?.name
                    || this.worlds.referenceTargets.find((target) => target.id === same)?.name
                : null;
            if (!this.edited) {
                return '';
            }
            const line = countsLine(previewCounts(this.edited), onto);
            return this.matchingStub ? `${line} · a stub named ${this.matchingStub.name} exists` : line;
        },
        // a fact's (or the summary's, or a draft fact's) edit form is
        // open: "Add fact" waits, so it never drops that unsaved edit
        factFormOpen() {
            return !!this.form && (!!this.form.factId || this.form.index != null);
        },
        // the open form's fact is no longer on the page (removed from its
        // own ⋯ menu, or not true at the date now viewed): the form goes
        // with it, so "Add fact" doesn't wait on a form nobody can see
        formTargetGone() {
            const form = this.form;
            if (!form) {
                return false;
            }
            if (form.factId) {
                const facts = [this.summaryFact, ...(this.shownFacts || []), ...(this.thing?.inherited || [])];
                return !facts.some((fact) => fact?.fact_id === form.factId);
            }
            if (form.index != null) {
                return !(this.draftRows || []).some((row) => row.index === form.index);
            }
            return false;
        },
        // while the page draft's nested "+ Add facts" draft is open or
        // held, its own Accept, Regenerate and version switch wait for it
        draftLocked() {
            return this.worlds.nestedHeld ? 'write or discard the added facts first' : null;
        },
        // mid-request, as DraftBar's: a Regenerate, accept or version
        // switch out
        draftBusy() {
            return this.worlds.previewPending || !!this.worlds.draft?.accepting || !!this.worlds.pending.use_version;
        },
        // the race's species, or the mix's first parent: this species
        heritagePreset() {
            return this.heritageCreating === 'mix' ? { parents: [this.thing.id] } : { species: this.thing.id };
        },
        // while a race/mix is drafted below the row, what follows the
        // section being created (the other Races/Mixes section, then
        // Named stubs) moves below the draft too, so nothing but the
        // section being created sits next to it
        heritageTailBelow() {
            return !this.draft && this.thing?.kind === 'species' && !!this.heritageCreating;
        },
        existence() {
            return existenceOf(this.thing);
        },
        existenceNote() {
            return EXISTENCE_NOTES[this.existence];
        },
        info() {
            return this.thing ? kindInfo(this.thing.kind) : null;
        },
        categories() {
            return this.info?.categories || [];
        },
        isLanguage() {
            return !this.draft && this.thing?.kind === 'language';
        },
        isHeritage() {
            return HERITAGE_KINDS.includes(this.thing?.kind);
        },
        // a kind that inherits, with something to inherit (a character
        // without heritage has none)
        showInherited() {
            return !this.draft && INHERITING_KINDS.includes(this.thing?.kind) && !!this.thing.inherited?.length;
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
        // a stub has nothing written yet to make prose from
        proseShown() {
            return this.thing?.stub && !this.draft ? {} : this.thing?.prose || {};
        },
        // the facts listed (`listedFacts`): the summary heads the page, and
        // a person's "but…" exceptions show under its "In" rows
        shownFacts() {
            return listedFacts(this.thing);
        },
        summaryFact() {
            return this.draft ? null : (this.thing?.facts || []).find((fact) => fact.summary) || null;
        },
        // the other name it's usually called by, if one is
        everydayName() {
            return (this.thing?.aka || []).find((entry) => entry.everyday)?.name || null;
        },
        otherNames() {
            return headerNames(this.thing?.aka);
        },
        // an other name given in one of the world's languages: that
        // language's name (languages 3a)
        otherNameLanguage() {
            const languages = this.worlds.things.language || [];
            return (index) => {
                const id = this.thing?.aka?.[index]?.language;
                return id ? languages.find((l) => l.id === id)?.name || '' : '';
            };
        },
        // what the numbers and other names editors show: a draft's own
        // fields are its copy's (`thing.numbers` resolved as rendered)
        numberFields() {
            return (this.draft ? this.edited?.fields : this.thing?.fields) || NO_FIELDS;
        },
        akaList() {
            return this.thing?.aka || NO_AKA;
        },
        editorBusy() {
            return this.draft ? this.draftBusy : !!this.worlds.pending.set_field;
        },
        // they start over on another thing, or another version of the draft
        editorKey() {
            return this.draft ? 'draft-' + (this.worlds.draft?.key ?? '') + '-' + (this.worlds.draft?.version ?? '') : this.thing?.id;
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
            return !this.draft && EDIT_ACTIONS.some((action) => this.worlds.pending[action]);
        },
        shownFields() {
            const calendar = this.worlds.calendar;
            const fields = [];
            for (const [name, value] of Object.entries(this.thing.fields)) {
                if (HIDDEN_FIELDS.includes(name) || value == null) {
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
        'thing.id'() {
            this.languageTab = 'about';
        },
        formTargetGone(gone) {
            if (gone) {
                this.form = null;
                this.afterSave = null;
            }
        },
        // another version of the draft: its forms and menus close
        'worlds.draft.version'() {
            if (this.draft) {
                this.form = null;
                this.selecting = false;
            }
        },
        thing(thing, before) {
            if (this.draft) {
                return;
            }
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
            if (!thing || thing.id !== before?.id) {
                this.merging = false;
                this.heritageCreating = null;
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
        repointedNote,
        addFiling,
        alsoHere,
        changeFiling,
        changeNewName,
        copyFactTo,
        holdFact,
        moveFactTo,
        removeDraftFact,
        removeFiling,
        repeatChoice,
        retarget,
        setFilingShowUnder,
        settleRepeat,
        tickFact,
        tickFileInto,
        // --- the draft mode: every change is the draft's own -------------
        edit(changes) {
            this.worlds.editDraft(changes);
        },
        // numbers and other names: the page writes them, a draft keeps them
        setNumber(field, value) {
            if (this.draft) {
                this.edit(setDraftNumber(this.edited, field, value));
            } else {
                this.worlds.setField(field, value);
            }
        },
        saveAka(aka) {
            if (this.draft) {
                this.edit(setDraftAka(this.edited, aka));
            } else {
                this.worlds.setAka(aka);
            }
        },
        setDraftKind(kind) {
            if (kind && kind !== this.edited.kind) {
                this.edit(changeKind(this.edited, kind));
            }
        },
        // an "In" row's change as the draft keeps it (dates without labels)
        draftFiling(change) {
            const out = { ...change };
            if ('since' in out) {
                out.since = dateIn(out.since);
            }
            return out;
        },
        // "+ In…" on a draft: the filing, then the group it shows under
        addDraftFiling(target, { showUnder = null, ...filing }) {
            let next = { ...this.edited, ...addFiling(this.edited, target, this.draftFiling(filing)) };
            if (showUnder) {
                const key = filingKey(target.newName
                    ? { target_id: null, new_name: { name: target.newName } }
                    : { target_id: target.id });
                next = { ...next, ...setFilingShowUnder(next, key, showUnder) };
            }
            this.edit({ filings: next.filings });
        },
        acceptDraft(intoStub = null) {
            this.worlds.acceptPreview(
                { name: this.edited.name.trim() },
                { open: !this.stay, intoStub, sameTargetId: intoStub ? null : this.edited._same || null },
            );
        },
        tickMove(factId, ticked) {
            const rows = tickMoveHere(this.edited, factId, ticked).move_here;
            this.edit(moveInEdit(this.edited, rows));
        },
        // the own fact replacing the inherited `row`, or -1
        overriderOf(row) {
            return this.edited.facts.findIndex((fact) => !fact.removed && (fact.overrides || []).includes(row.fact_id));
        },
        // ticked: inherited as it is; unticked: replaced by an own fact
        // the inherited `row` as its line takes it: as the server's page
        // of the draft sends it (`draft.page.inherited`, as a saved page
        // sends its own: category, dates, linked words), else the row
        // itself. (`thing.inherited` is empty on a draft: it lists them
        // here, not in ThingInherited.)
        inheritedLine(row) {
            const sent = (this.worlds.draft?.page?.inherited || []).find((item) => item.fact_id === row.fact_id);
            return sent || { rendered: row.text, category: row.category, source_id: row.source_id, source_name: row.source };
        },
        setKept(row, kept) {
            this.worlds.setPreviewOverride(row.fact_id, kept ? null : defaultOverrideIndex(this.edited, row));
        },
        // the draft's fact form: the page's (`ThingFactForm`), its words
        // plain (a draft's are linked by name on accept)
        startDraftForm(row, mode) {
            const fact = row.fact;
            this.form = {
                mode,
                draft: true,
                index: row.index,
                category: fact.category,
                text: fact.text,
                fromYear: yearOf(fact.since),
                untilYear: yearOf(fact.until) ?? (mode === 'end' ? yearOf(this.worlds.currentWorld?.now) : null),
                picks: {},
                refs: {},
                links: [],
                stubs: [],
            };
        },
        saveDraftForm() {
            const form = this.form;
            const year = (value) => (this.validYear(value) ? dateOf(value) : null);
            const change = {};
            if (form.mode === 'edit' || form.mode === 'add') {
                const text = form.text.trim();
                if (!text) {
                    return;
                }
                change.text = text;
                change.category = form.category;
                // the names the owner picked in it link by name on accept
                const links = linkPayload(this.worlds.matchesFor(form.text, null), form.picks || {}, form.refs || {}, text);
                if (Object.keys(links.picks).length) {
                    this.edit({ picks: { ...(this.edited.picks || {}), ...links.picks } });
                }
                if (links.newNames.length) {
                    this.edit({ treated_as_new: [...new Set([...(this.edited.treated_as_new || []), ...links.newNames])] });
                }
            }
            if (form.mode !== 'end') {
                change.since = year(form.fromYear);
            }
            change.until = year(form.untilYear);
            if (form.mode === 'add') {
                // "+ Add fact" on a draft: a new local fact, not an edit
                // to an existing row (nothing is written before Accept)
                this.edit(addDraftFact(this.edited, { category: change.category, text: change.text, valid_from: change.since, valid_until: change.until }));
            } else {
                this.edit(editFact(this.edited, form.index, change));
            }
            this.form = null;
        },
        // the page's fact as FactRow shows it
        factView(fact) {
            return { ...fact, text: fact.rendered };
        },
        setExistence(value) {
            if (value && value !== this.existence) {
                this.worlds.setField('existence', value);
            }
        },
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
        nameItOwnName() {
            const mark = this.nameFlag;
            this.worlds.openNameIt({
                words: mark.part || mark.name,
                languageId: (this.edited.languages || [])[0]?.language || (this.edited.inherited_languages || [])[0]?.language_id || null,
                kind: this.edited.kind,
                markId: mark.id,
                target: { draftKey: this.worlds.draft?.key },
            });
        },
        nameItThing() {
            const own = this.thing.languages_own || [];
            const seen = (this.thing.languages_view || []).map((r) => ({ language: r.language_id }));
            this.worlds.openNameIt({
                words: this.thing.name,
                languageId: [...own, ...seen][0]?.language || null,
                kind: this.thing.kind,
                // the panel can rename only part of it (owner, Test3)
                target: { thingId: this.thing.id, fullName: this.thing.name },
                stub: !!this.thing.stub,
            });
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
            // a fact's edit form is open: adding would drop its edit
            if (this.factFormOpen) {
                return;
            }
            this.form = {
                mode: 'add',
                ...(this.draft ? { draft: true } : {}),
                category: this.categories[0],
                text: '',
                fromYear: null,
                untilYear: null,
                picks: {},
                refs: {},
                links: [],
                stubs: [],
            };
        },
        // `mode` 'dates': "Change dates", the dates alone
        startEdit(fact, mode = 'edit') {
            const { text, links } = this.editState(fact);
            this.form = {
                mode,
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
            if (this.form?.draft) {
                this.saveDraftForm();
                return;
            }
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
        repointLink(fact, { index, to, mode = null, useName = null }) {
            const occurrence = refOccurrence(fact.text, fact.segments, index);
            if (occurrence !== null && to !== fact.segments[index].ref) {
                this.worlds.repointRef(fact.fact_id, occurrence, to, { mode, useName });
            }
        },
        // words selected in the fact `fact` (`LinkedText`'s `select`)
        selected(fact, { start, end, words, before = '', x, y }) {
            this.selection = { factId: fact.fact_id, start, end, words, before, target: [x, y] };
            this.selecting = true;
        },
        // words selected in a drafted fact: the server's copy is what a
        // selection names, so a fact written or rewritten here has none
        selectedDraft(row, { start, end, words, before = '', x, y }) {
            this.selection = {
                index: row.serverIndex,
                start,
                end,
                words,
                before,
                target: [x, y],
                // linked words: Name it… names that entry (final review 4)
                link: linkAt(row.view?.segments, start, end),
                blocked: row.serverIndex === null ? 'This fact was written or changed here: its words can be linked once it\'s accepted.' : '',
            };
            this.selecting = true;
        },
        makeStub(expand, { kind, tag }) {
            const found = this.selection;
            if (found && this.draft) {
                if (found.index !== null) {
                    this.worlds.draftSelection('make_stub_from_text', found.index, found.start, found.end, { kind, ...(tag ? { tag } : {}) });
                }
                return;
            }
            if (found) {
                const words = found.words.trim().split(/\s+/).join(' ');
                this.worlds.makeStubFromText(found.factId, found.start, found.end, kind, tag, { expand, words });
            }
        },
        // `mode` (P4, ruling H2): 'link' as written, 'name' taught as
        // another name too, 'rename' to `useName`, one of the target's names
        linkWords({ target, mode = 'link', useName = null }) {
            const found = this.selection;
            if (found && this.draft) {
                if (found.index !== null && mode !== 'rename') {
                    this.worlds.draftSelection('link_text', found.index, found.start, found.end, { target_id: target.id, mode });
                }
                return;
            }
            if (found) {
                this.worlds.linkText(found.factId, found.start, found.end, target.id, { mode, useName });
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
/* under the heading's other parts, on a line of its own */
.name-flag-row {
    order: 1;
}
.name-flagged {
    text-decoration: underline wavy rgb(var(--v-theme-warning));
    text-underline-offset: 3px;
}
.draft-name {
    max-width: 340px;
}

.draft-kind {
    flex: none;
    width: 150px;
}

.stub-fact {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 2px 0;
}

.override-by {
    width: 220px;
}

.file-into-name {
    font-weight: 600;
    color: rgb(var(--v-theme-link));
}

/* an unticked row's name greys with the rest of its row */
.suggestion-dropped .file-into-name,
.suggestion-offer .file-into-name {
    color: inherit;
}

.role {
    font-style: italic;
    color: rgb(var(--v-theme-muted));
}

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

.held {
    margin-left: 6px;
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
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

.summary-text {
    font-size: 15px;
    line-height: 1.5;
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
