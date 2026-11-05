<template>
    <div class="person-name mt-3" data-testid="person-name">
        <div class="d-flex align-center flex-wrap ga-2">
            <span class="text-overline text-muted">Name</span>
            <span class="text-caption text-muted" data-testid="person-name-rule">
                {{ view.language.name }}<template v-if="view.rule_name"> · {{ view.rule_name }}</template>
            </span>
            <v-spacer></v-spacer>
            <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-rename" data-testid="person-name-it" @click="$emit('name-it')">Name it…</v-btn>
        </div>

        <div v-if="!parts.length" class="text-body-2 text-muted" data-testid="person-name-none">Not built from a rule.</div>
        <!-- one column per part, fixed: editing a part never moves the others -->
        <div v-else class="parts" :style="{ gridTemplateColumns: `repeat(${parts.length}, minmax(0, 1fr))` }">
            <div
                v-for="(part, index) in parts"
                :key="index"
                class="part pa-2"
                :class="{ inherited: part.source === 'inherited', fixed: part.source === 'word' }"
                data-testid="person-name-part"
            >
                <div class="d-flex align-center text-caption text-muted">
                    <span class="label">{{ part.label }}</span>
                    <v-spacer></v-spacer>
                    <v-btn
                        v-if="part.source !== 'word' && editing !== index"
                        icon="mdi-pencil"
                        variant="text"
                        size="x-small"
                        density="compact"
                        :aria-label="'Change the ' + part.label"
                        data-testid="person-name-part-edit"
                        @click="startEdit(index, part)"
                    ></v-btn>
                </div>
                <v-text-field
                    v-if="editing === index"
                    v-model="typed"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    data-testid="person-name-part-input"
                    @keydown.enter="saveEdit(index)"
                    @keydown.esc="editing = null"
                    @blur="editing = null"
                ></v-text-field>
                <div v-else class="text" :title="part.written !== part.text ? `${part.text} in ${view.language.name}` : undefined">{{ part.written }}</div>
                <div class="source text-caption" :class="{ 'from-link': part.source === 'inherited' }">
                    <a v-if="part.source === 'inherited' && part.from_id" href="#" class="thing-link" @click.prevent="worlds.openThing(part.from_id)">{{ sourceLine(part) }}</a>
                    <span v-else class="text-muted">{{ sourceLine(part) }}</span>
                </div>
            </div>
        </div>

        <!-- what the name is built as: changing it doesn't rename -->
        <div v-if="parts.length && choiceKeys.length" class="d-flex align-center flex-wrap ga-1 mt-2" data-testid="person-built-as">
            <span class="text-caption text-muted">built as:</span>
            <v-menu v-for="key in choiceKeys" :key="key" location="bottom start">
                <template #activator="{ props: menu }">
                    <v-chip v-bind="menu" size="small" variant="outlined" :data-testid="'person-built-as-' + key">{{ view.built_as[key] || view.choices[key][0] }}</v-chip>
                </template>
                <v-list density="compact">
                    <v-list-item
                        v-for="value in view.choices[key]"
                        :key="value"
                        :title="value"
                        :active="value === view.built_as[key]"
                        @click="worlds.personBuiltAs(thing.id, { ...view.built_as, [key]: value })"
                    ></v-list-item>
                </v-list>
            </v-menu>
        </div>

        <!-- the pet name: from the language's rule, or the owner's own -->
        <div class="d-flex align-center flex-wrap ga-1 mt-2" data-testid="person-pet-name">
            <span class="text-caption text-muted">pet name:</span>
            <template v-if="editingPet">
                <v-text-field
                    v-model="petTyped"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="pet-input"
                    data-testid="person-pet-input"
                    @keydown.enter="savePet"
                    @keydown.esc="editingPet = false"
                ></v-text-field>
            </template>
            <template v-else-if="pet">
                <span class="pet" data-testid="person-pet">{{ pet.name }}</span>
                <span class="text-caption text-muted">
                    <template v-if="view.pet_used_by.length">· used by {{ view.pet_used_by.join(', ') }}</template>
                    · {{ pet.rule ? 'from the language’s rule' : 'your own' }}
                </span>
            </template>
            <span v-else class="text-caption text-muted">none</span>
            <v-btn
                v-if="!editingPet"
                icon="mdi-dice-5-outline"
                variant="text"
                size="x-small"
                density="compact"
                aria-label="Roll a pet name from the language's rule"
                title="Roll a pet name from the language's rule"
                data-testid="person-pet-roll"
                @click="worlds.personPetName(thing.id, 'roll')"
            ></v-btn>
            <v-btn
                v-if="!editingPet"
                icon="mdi-pencil"
                variant="text"
                size="x-small"
                density="compact"
                aria-label="Type a pet name"
                data-testid="person-pet-edit"
                @click="startPet"
            ></v-btn>
        </div>

        <!-- titles held: at most one shown with the name -->
        <div class="mt-2" data-testid="person-titles">
            <div class="d-flex align-center flex-wrap ga-1">
                <span class="text-caption text-muted">titles:</span>
                <span v-if="!titles.length && !addingTitle" class="text-caption text-muted">none</span>
                <v-chip
                    v-for="title in titles"
                    :key="title.name"
                    size="small"
                    :variant="title.shown ? 'flat' : 'outlined'"
                    :color="title.shown ? 'accent' : undefined"
                    closable
                    :title="titleHint(title)"
                    data-testid="person-title"
                    @click="toggleShown(title)"
                    @click:close="worlds.personTitleRemove(thing.id, title.name)"
                >{{ title.name }}<span v-if="title.shown" class="ml-1 text-caption">· {{ title.shown }}</span></v-chip>
                <v-btn v-if="!addingTitle" variant="text" size="x-small" color="accent" prepend-icon="mdi-plus" data-testid="person-title-add" @click="startTitle">Title</v-btn>
            </div>
            <div v-if="addingTitle" class="d-flex align-center flex-wrap ga-2 mt-1" data-testid="person-title-form">
                <v-text-field
                    v-model="titleText"
                    label="A title, in English"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="title-input"
                    data-testid="person-title-input"
                    @update:model-value="offerKept"
                    @keydown.enter="saveTitle(titleText)"
                    @keydown.esc="addingTitle = false"
                ></v-text-field>
                <v-chip
                    v-if="kept"
                    size="small"
                    variant="tonal"
                    color="accent"
                    :title="`${view.language.name} keeps its own word for ${kept.english}`"
                    data-testid="person-title-kept"
                    @click="saveTitle(kept.word, kept.language_id)"
                >use {{ kept.word }}</v-chip>
                <v-btn size="small" variant="tonal" color="accent" :disabled="!titleText.trim()" @click="saveTitle(titleText)">Add</v-btn>
                <v-btn size="small" variant="text" data-testid="person-title-meaning" @click="titleFromMeaning">From a meaning in {{ view.language.name }}…</v-btn>
                <v-btn size="small" variant="text" @click="addingTitle = false">Cancel</v-btn>
            </div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { partSourceLine, pronounOf } from './personName.js';

// A person's Name section (languages 4b-2, mockup B): their name in
// labelled parts, each editable (the name follows), inherited parts saying
// where they came from; what it's built as; their pet name; the titles
// they hold. `thing`: the page, with `name_view`, `aka` and `calls`.
export default {
    name: 'PersonName',
    props: {
        thing: { type: Object, required: true },
    },
    emits: ['name-it'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { editing: null, typed: '', editingPet: false, petTyped: '', addingTitle: false, titleText: '' };
    },
    computed: {
        view() {
            return this.thing.name_view;
        },
        parts() {
            return this.view?.parts || [];
        },
        choiceKeys() {
            return Object.keys(this.view?.choices || {});
        },
        pronoun() {
            return pronounOf(this.view?.built_as);
        },
        titles() {
            return (this.thing.aka || []).filter((a) => a.kind === 'title');
        },
        pet() {
            return (this.thing.aka || []).find((a) => a.kind === 'pet' && !a.by) || null;
        },
        kept() {
            const offer = this.worlds.keptTitleOffer;
            return offer && offer.word && offer.english === this.titleText.trim() ? offer : null;
        },
    },
    methods: {
        sourceLine(part) {
            return partSourceLine(part, this.view.sources, this.pronoun);
        },
        startEdit(index, part) {
            this.editing = index;
            this.typed = part.text;
        },
        saveEdit(index) {
            const text = this.typed.trim();
            if (text && text !== this.parts[index].text) this.worlds.personNamePart(this.thing.id, index, text);
            this.editing = null;
        },
        startPet() {
            this.petTyped = this.pet?.name || '';
            this.editingPet = true;
        },
        savePet() {
            if (this.petTyped.trim()) this.worlds.personPetName(this.thing.id, 'set', this.petTyped.trim());
            this.editingPet = false;
        },
        startTitle() {
            this.titleText = '';
            this.addingTitle = true;
        },
        offerKept(text) {
            clearTimeout(this.keptTimer);
            this.keptTimer = setTimeout(() => this.worlds.personKeptTitle(this.thing.id, text || ''), 300);
        },
        saveTitle(name, languageId = null) {
            if (!name.trim()) return;
            this.worlds.personTitleAdd(this.thing.id, { name: name.trim(), ...(languageId ? { language_id: languageId } : {}) });
            this.addingTitle = false;
        },
        toggleShown(title) {
            const next = { undefined: 'before', before: 'after', after: null }[title.shown];
            this.worlds.personTitleAdd(this.thing.id, { ...title, shown: next });
        },
        titleHint(title) {
            const parts = [];
            if (title.meaning) parts.push(`“${title.meaning}”`);
            parts.push(title.shown ? `shown ${title.shown} the name; click to change` : 'click to show it with the name');
            return parts.join(' · ');
        },
        titleFromMeaning() {
            this.addingTitle = false;
            this.worlds.openNameIt({
                words: '',
                languageId: this.view.language.id,
                kind: 'character',
                target: { titleOf: this.thing.id },
                title: true,
            });
        },
    },
};
</script>

<style scoped>
.parts {
    display: grid;
    gap: 8px;
}
.part {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    min-width: 0;
}
.part.inherited {
    border-color: rgb(var(--v-theme-link));
}
.part.fixed {
    border-style: dashed;
}
.part .text {
    font-size: 1.05rem;
    overflow-wrap: anywhere;
}
.part .label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.pet {
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
}
.pet-input,
.title-input {
    max-width: 240px;
}
</style>
