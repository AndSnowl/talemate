<template>
    <div class="name-builder" data-testid="name-builder">
        <div v-if="!parts.length" class="text-body-2 text-muted">Rolling…</div>
        <!-- one grid: every part has the same rows at the same heights, so
             nothing moves between rolls (mockup 2026-11-03-…-stable-grid) -->
        <div v-else class="grid" :style="{ gridTemplateColumns: columns }">
            <div v-for="(part, c) in parts" :key="part.index" class="part" data-testid="name-builder-part">
                <!-- 1: what it is -->
                <div class="cell title" :style="at(c, 1)" :title="titleOf(part, c)">
                    <span class="title-text">{{ titleOf(part, c) }}</span>
                    <v-btn
                        v-if="part.kind === 'connection' && part.source === 'inherited' || inheritedFree(part)"
                        :icon="inheritedFree(part) ? 'mdi-pin-outline' : 'mdi-pin'"
                        variant="text"
                        size="x-small"
                        density="compact"
                        :aria-label="(inheritedFree(part) ? 'Take it from ' : 'Let it roll, not from ') + (part.from_role || 'the connection')"
                        data-testid="name-builder-inherited-pin"
                        @click="freePart(part)"
                    ></v-btn>
                    <v-btn
                        v-else-if="part.kind === 'rule' || part.kind === 'connection'"
                        :icon="pinned(part) ? 'mdi-pin' : 'mdi-pin-outline'"
                        variant="text"
                        size="x-small"
                        density="compact"
                        :aria-label="(pinned(part) ? 'Unpin ' : 'Pin ') + part.label"
                        data-testid="name-builder-pin"
                        @click="worlds.nameItPinPart(part.index, chosen(part))"
                    ></v-btn>
                </div>
                <!-- 2: how it's filled -->
                <div class="cell what" :style="at(c, 2)" :title="whatOf(part)">{{ whatOf(part) }}</div>
                <!-- 3: the box -->
                <div v-if="part.kind === 'word'" class="fixed-word" :style="at(c, 3)">{{ part.english || part.rolls[0]?.text }}</div>
                <v-text-field
                    v-else-if="part.kind === 'meaning'"
                    :model-value="worlds.nameItPartMeanings[part.index] || ''"
                    placeholder="a meaning…"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="box"
                    :style="at(c, 3)"
                    data-testid="name-builder-meaning"
                    @keydown.enter="find(part, $event.target.value)"
                    @change="draft[part.index] = $event.target.value"
                    @update:model-value="draft[part.index] = $event"
                >
                    <template #append-inner>
                        <v-btn size="x-small" variant="outlined" color="accent" :loading="!!worlds.nameItPartPending[part.index]" data-testid="name-builder-find" @click="find(part)">Find</v-btn>
                    </template>
                </v-text-field>
                <v-text-field
                    v-else
                    :model-value="worlds.nameItPartPinned[part.index] || ''"
                    placeholder="your own name…"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="box"
                    :style="at(c, 3)"
                    data-testid="name-builder-type"
                    @change="worlds.nameItTypePart(part.index, $event.target.value)"
                ></v-text-field>
                <!-- 4…11: eight roll rows, blank ones kept -->
                <template v-if="part.kind !== 'word'">
                    <div
                        v-for="(row, r) in rowsOf(part)"
                        :key="r"
                        class="roll"
                        :class="{ cur: row && row.text === chosen(part), pinned: row && row.text === worlds.nameItPartPinned[part.index] }"
                        :style="at(c, 4 + r)"
                        :title="row ? row.text + (row.meaning ? ' · ' + row.meaning : '') : ''"
                        :data-testid="row ? 'name-builder-roll' : undefined"
                        @click="row && worlds.nameItChoosePart(part.index, row.text)"
                    >
                        <template v-if="row">
                            <span class="roll-text">{{ row.text }}</span>
                            <v-icon
                                size="x-small"
                                class="pin"
                                :aria-label="'Pin ' + row.text"
                                data-testid="name-builder-roll-pin"
                                @click.stop="worlds.nameItPinPart(part.index, row.text)"
                            >{{ row.text === worlds.nameItPartPinned[part.index] ? 'mdi-pin' : 'mdi-pin-outline' }}</v-icon>
                        </template>
                    </div>
                </template>
                <!-- 12: how it's built (a meaning part), or why it couldn't -->
                <div
                    v-if="part.kind === 'meaning'"
                    class="cell note"
                    :class="{ 'text-error': !!worlds.nameItPartError[part.index] }"
                    :style="at(c, 12)"
                    :title="noteOf(part)"
                    data-testid="name-it-working"
                >{{ noteOf(part) }}</div>
            </div>
        </div>
        <div v-if="built" class="d-flex align-center ga-3 mt-3 built-row">
            <span class="built" :title="built" data-testid="name-it-built">{{ built }}</span>
            <v-btn size="small" color="accent" variant="flat" data-testid="name-it-use" @click="use">Use this name</v-btn>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

const ROWS = 8;

// The Name it… builder (languages 4b-1; owner 2026-11-03, mockups
// docs/superpowers/mockups/2026-11-03-languages-4b1-builder-meaning-per-part.html
// and …-builder-stable-grid.html): a composed rule's name part by part,
// on one grid whose rows never change height. A rule part rolls (pin one,
// or type your own); a fixed word shows what it means; a meaning part has
// its own meaning box, whose Find fills that part only. Use this name puts
// the name where the request asked (`worlds.pickNameIt`).
export default {
    name: 'NameBuilder',
    props: {
        languageId: { type: String, default: null },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        // what's typed in each meaning box, before Find
        return { draft: {} };
    },
    computed: {
        parts() {
            return this.worlds.nameItParts?.parts || [];
        },
        // a fixed word's column is narrow; the others share the rest
        columns() {
            return this.parts.map((p) => (p.kind === 'word' ? '96px' : 'minmax(0, 1fr)')).join(' ');
        },
        built() {
            return this.worlds.nameItBuilt;
        },
    },
    methods: {
        at(column, row) {
            return { gridColumn: column + 1, gridRow: row };
        },
        chosen(part) {
            return this.worlds.nameItPartChosen[part.index] || '';
        },
        pinned(part) {
            return !!this.worlds.nameItPartPinned[part.index];
        },
        meaningOfWord(part) {
            return part.rolls[0]?.parts?.[0]?.meaning || '';
        },
        titleOf(part, c) {
            if (part.kind === 'word') return part.rolls[0]?.text || '';
            if (part.kind === 'meaning') {
                const before = this.parts[c - 1];
                return before && before.kind === 'word' ? `What “${before.rolls[0]?.text} …” means` : 'What it means';
            }
            return part.label;
        },
        // an inherited part the owner set free to roll (languages 4b-2)
        inheritedFree(part) {
            return part.kind === 'connection' && this.worlds.nameItPartFree.includes(part.index);
        },
        freePart(part) {
            this.worlds.nameItFreePart(part.index);
            this.worlds.nameItRollParts(this.languageId, this.worlds.nameItParts?.rule_id);
        },
        whatOf(part) {
            if (part.source === 'inherited') return 'inherited · unpin to roll it';
            if (part.kind === 'word') {
                const meaning = this.meaningOfWord(part);
                return meaning ? `always · “${meaning}”` : 'always';
            }
            if (part.kind === 'meaning') return 'a meaning in English · empty: rolled';
            return 'rolled · pin one, or type your own';
        },
        // eight rows: the rolls, then blanks
        rowsOf(part) {
            const rows = part.rolls.slice(0, ROWS).map((roll) => ({
                text: roll.text,
                meaning: (roll.parts || []).map((p) => `${p.word} “${p.meaning}”`).join(' + '),
            }));
            while (rows.length < ROWS) rows.push(null);
            return rows;
        },
        noteOf(part) {
            const error = this.worlds.nameItPartError[part.index];
            if (error) return error;
            const roll = part.rolls.find((r) => r.text === this.chosen(part));
            if (!roll || !(roll.parts || []).length) return '';
            const said = roll.parts
                .map((p) => `${p.word} “${p.meaning}”${(p.steps || []).length ? ' + ' + p.steps.join(' + ') : ''}${p.new ? ' (new word, saved if you use the name)' : ''}`)
                .join(' + ');
            const how = this.worlds.nameItPartMeanings[part.index] ? '' : ': rolled from the dictionary';
            return said + how;
        },
        find(part, typed) {
            const text = typed ?? this.draft[part.index] ?? this.worlds.nameItPartMeanings[part.index] ?? '';
            this.worlds.nameItPartMeaning(this.languageId, this.worlds.nameItParts?.rule_id, part.index, text);
        },
        use() {
            const from = this.worlds.nameItBuiltFrom;
            const coined = from.filter((p) => p.new).map((p) => ({ word: p.word, meaning: p.meaning }));
            const meaning = from.map((p) => p.meaning).join(' ');
            this.worlds.pickNameIt(this.languageId, this.built, meaning, coined);
        },
    },
};
</script>

<style scoped>
.grid {
    display: grid;
    grid-template-rows: 22px 18px 40px repeat(8, 26px) 18px;
    column-gap: 10px;
    row-gap: 2px;
}
.part {
    display: contents;
}
.cell {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
.title {
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
    font-size: 0.85rem;
}
.title-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1 1 auto;
}
.what {
    font-size: 0.75rem;
    color: rgb(var(--v-theme-muted, var(--v-theme-on-surface)));
    opacity: 0.85;
}
.box {
    min-width: 0;
}
.fixed-word {
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 4px;
    font-size: 1rem;
}
.roll {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-width: 0;
    padding: 0 8px;
    border-radius: 4px;
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
    cursor: pointer;
}
.roll:empty {
    cursor: default;
}
.roll.cur {
    background: rgb(var(--v-theme-foreign));
    color: rgb(var(--v-theme-surface));
    font-style: normal;
}
.roll.pinned {
    outline: 1px solid rgb(var(--v-theme-foreign));
}
.roll-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.pin {
    font-style: normal;
    opacity: 0.8;
}
.note {
    font-size: 0.75rem;
    opacity: 0.85;
}
.built-row {
    min-width: 0;
}
.built {
    font-size: 1.15rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
</style>
