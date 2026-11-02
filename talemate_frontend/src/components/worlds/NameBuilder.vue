<template>
    <div class="name-builder" data-testid="name-builder">
        <div v-if="!parts.length" class="text-body-2 text-muted">Rolling…</div>
        <div class="columns">
            <div v-for="part in parts" :key="part.index" class="column" :class="{ fixed: part.kind === 'word' }" data-testid="name-builder-part">
                <div class="d-flex align-center ga-1">
                    <span class="text-caption text-muted label">{{ part.label }}</span>
                    <v-btn
                        v-if="part.kind !== 'word'"
                        :icon="pinned(part) ? 'mdi-pin' : 'mdi-pin-outline'"
                        variant="text"
                        size="x-small"
                        density="compact"
                        :aria-label="(pinned(part) ? 'Unpin ' : 'Pin ') + part.label"
                        data-testid="name-builder-pin"
                        @click="worlds.nameItPinPart(part.index, chosen(part))"
                    ></v-btn>
                </div>
                <template v-if="part.kind === 'word'">
                    <span class="word">{{ part.rolls[0]?.text }}</span>
                </template>
                <template v-else>
                    <v-text-field
                        :model-value="worlds.nameItPartPinned[part.index] || ''"
                        placeholder="your own word"
                        density="compact"
                        variant="outlined"
                        hide-details
                        class="own"
                        data-testid="name-builder-type"
                        @change="worlds.nameItTypePart(part.index, $event.target.value)"
                    ></v-text-field>
                    <NameRolls
                        :items="rollsOf(part)"
                        :current="chosen(part)"
                        testid="name-builder-roll"
                        pin-testid="name-builder-roll-pin"
                        class="mt-1"
                        @pick="worlds.nameItChoosePart(part.index, $event.name)"
                        @pin="worlds.nameItPinPart(part.index, $event.name)"
                    />
                </template>
            </div>
        </div>
        <div v-if="built" class="d-flex align-center flex-wrap ga-3 mt-3">
            <span class="built" data-testid="name-it-built">{{ built }}</span>
            <v-btn size="small" color="accent" variant="flat" data-testid="name-it-use" @click="use">Use this name</v-btn>
            <span v-if="builtFrom.length" class="text-caption text-muted" data-testid="name-it-working">
                <template v-for="(part, i) in builtFrom" :key="i"><span v-if="i"> + </span><span class="foreign">{{ part.word }}</span> “{{ part.meaning }}”<span v-for="step in part.steps || []" :key="step"> + {{ step }}</span><span v-if="part.new"> (new word, saved if you pick it)</span></template>
            </span>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import NameRolls from './NameRolls.vue';

// The Name it… builder (languages 4b-1, mockup B): a composed rule's name
// laid out part by part, each with its rolls (`NameRolls`, as the batch
// shows them), a pin, and a box for the owner's own word (which pins it).
// Reroll (the panel's) rolls every unpinned part; the built name shows
// below with how its meaning parts are built, and Use this name puts it
// where the request asked (`worlds.pickNameIt`).
export default {
    name: 'NameBuilder',
    components: { NameRolls },
    props: {
        languageId: { type: String, default: null },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        parts() {
            return this.worlds.nameItParts?.parts || [];
        },
        built() {
            return this.worlds.nameItBuilt;
        },
        builtFrom() {
            return this.worlds.nameItBuiltFrom;
        },
    },
    methods: {
        chosen(part) {
            return this.worlds.nameItPartChosen[part.index] || '';
        },
        pinned(part) {
            return !!this.worlds.nameItPartPinned[part.index];
        },
        rollsOf(part) {
            const pinned = this.worlds.nameItPartPinned[part.index];
            return part.rolls.map((roll) => ({
                name: roll.text,
                meaning: (roll.parts || []).map((p) => p.meaning).join(' '),
                pinned: roll.text === pinned,
            }));
        },
        use() {
            const from = this.builtFrom;
            const coined = from.filter((p) => p.new).map((p) => ({ word: p.word, meaning: p.meaning }));
            const meaning = from.map((p) => p.meaning).join(' ');
            this.worlds.pickNameIt(this.languageId, this.built, meaning, coined);
        },
    },
};
</script>

<style scoped>
.columns {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: flex-start;
}
.column {
    flex: 1 1 200px;
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 6px;
    padding: 6px 8px;
}
.column.fixed {
    flex: 0 0 auto;
    border-style: dashed;
}
.label {
    flex: 1 1 auto;
}
.word {
    font-size: 1.05rem;
}
.own {
    max-width: 220px;
}
.built {
    font-size: 1.15rem;
    font-weight: 600;
}
.foreign {
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
}
</style>
