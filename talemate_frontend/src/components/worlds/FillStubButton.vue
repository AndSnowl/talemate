<template>
    <v-btn
        variant="outlined"
        size="small"
        color="accent"
        :loading="loading"
        :disabled="disabled"
        :title="title"
        :data-testid="testid"
        @click="$emit('fill')"
    >Fill stub “{{ name }}”</v-btn>
</template>

<script>
// "Fill stub X": another way to accept a draft named like a stub of its
// kind (the stub becomes the entry), so it sits right by Accept, in the
// draft bar and again at the draft's foot (polish 3).
export default {
    name: 'FillStubButton',
    props: {
        name: { type: String, required: true },
        disabled: { type: Boolean, default: false },
        title: { type: String, default: null },
        loading: { type: Boolean, default: false },
        testid: { type: String, default: 'fill-stub-instead' },
    },
    emits: ['fill'],
};
</script>
