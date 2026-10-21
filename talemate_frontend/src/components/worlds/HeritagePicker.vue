<template>
    <div class="heritage-picker d-flex align-center flex-wrap ga-2" data-testid="heritage-picker">
        <v-autocomplete
            v-for="(label, index) in shownLabels"
            :key="index"
            :model-value="modelValue[index] || null"
            :label="label"
            :items="itemsFor(index)"
            item-title="name"
            item-value="id"
            :item-props="itemProps"
            clearable
            density="compact"
            variant="outlined"
            hide-details
            class="parent"
            :disabled="disabled"
            :data-testid="'heritage-parent-' + (index + 1)"
            @update:model-value="set(index, $event)"
        ></v-autocomplete>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

const LABELS = {
    character: ['Heritage', 'Second parent'],
    mix: ['First parent', 'Second parent'],
};

// The create box's heritage picker: one or two parents, each searchable
// over the world's species, races and mixes (`worlds.heritage`). A
// character shows the second parent once the first is picked; a mix always
// has both. The value is the list of picked ids, in order.
export default {
    name: 'HeritagePicker',
    props: {
        modelValue: { type: Array, required: true },
        kind: { type: String, default: 'character' },
        disabled: { type: Boolean, default: false },
    },
    emits: ['update:modelValue'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        labels() {
            return LABELS[this.kind] || LABELS.character;
        },
        shownLabels() {
            return this.kind === 'mix' || this.modelValue[0] ? this.labels : this.labels.slice(0, 1);
        },
    },
    methods: {
        // a parent can't be picked twice
        itemsFor(index) {
            const other = this.modelValue[1 - index];
            return this.worlds.heritage.filter((item) => item.id !== other);
        },
        // "race of Human", "mix of Human and Orc", "species". A picked id
        // not listed yet (a mix just made, before `list_heritage` answers)
        // comes as the bare id.
        itemProps(item) {
            if (!item || typeof item !== 'object') {
                return {};
            }
            const species = item.species_ids
                .filter((id) => id !== item.id)
                .map((id) => this.worlds.heritage.find((other) => other.id === id)?.name)
                .filter(Boolean);
            const of = item.kind === 'species' || !species.length ? '' : ` of ${species.join(' and ')}`;
            return { subtitle: `${item.kind}${of}` };
        },
        set(index, id) {
            const picked = [...this.modelValue];
            picked[index] = id || null;
            // clearing the first parent moves the second up
            this.$emit('update:modelValue', picked.filter(Boolean));
        },
    },
};
</script>

<style scoped>
.parent {
    min-width: 200px;
    max-width: 260px;
}
</style>
