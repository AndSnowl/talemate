<template>
    <div class="name-rolls">
        <v-chip
            v-for="item in items"
            :key="item.name"
            class="name"
            :class="{ pinned: item.pinned }"
            :variant="item.name === current ? 'flat' : item.pinned ? 'outlined' : 'tonal'"
            :color="item.name === current ? 'accent' : undefined"
            :title="item.meaning || 'no meaning of its own'"
            :data-testid="testid"
            @click="$emit('pick', item)"
        >{{ item.name }}<v-btn
                :icon="item.pinned ? 'mdi-pin' : 'mdi-pin-outline'"
                variant="text"
                size="x-small"
                density="compact"
                class="ml-1 pin"
                :aria-label="(item.pinned ? 'Unpin ' : 'Pin ') + item.name"
                :data-testid="pinTestid"
                @click.stop="$emit('pin', item)"
            ></v-btn></v-chip>
    </div>
</template>

<script>
// A batch of rolled names (Name it…, owner Test3): each a chip that picks
// it, with a pin that keeps it through a reroll; the pinned come first
// (the store's `nameItShown`, `nameItWordShown`). `current`: the one in use.
export default {
    name: 'NameRolls',
    props: {
        items: { type: Array, required: true },
        current: { type: String, default: '' },
        testid: { type: String, default: 'name-it-name' },
        pinTestid: { type: String, default: 'name-it-pin' },
    },
    emits: ['pick', 'pin'],
};
</script>

<style scoped>
.name-rolls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.pin {
    font-style: normal;
}
.name {
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
}
</style>
