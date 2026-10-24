<template>
    <span ref="anchor" class="fact-menu-anchor">
    <v-menu v-model="open" :target="point || undefined" :close-on-content-click="false" location="bottom end">
        <template #activator="{ props }">
            <v-btn
                v-bind="props"
                icon="mdi-dots-horizontal"
                variant="text"
                size="x-small"
                density="comfortable"
                aria-label="Fact menu"
                title="Move, copy, hold, edit…"
                data-testid="fact-menu-button"
                @click="show(null)"
            ></v-btn>
        </template>

        <!-- the menu -->
        <v-card v-if="mode === 'list'" class="fact-menu" min-width="230" data-testid="fact-menu" @keydown.esc="open = false">
            <v-list density="compact" role="menu">
                <v-list-item prepend-icon="mdi-arrow-right-bold-box-outline" title="Move to…" role="menuitem" data-testid="fact-move" @click="mode = 'move'"></v-list-item>
                <v-list-item prepend-icon="mdi-content-duplicate" title="Copy to…" role="menuitem" data-testid="fact-copy" @click="mode = 'copy'"></v-list-item>
                <v-list-item prepend-icon="mdi-account-voice" title="Held by…" role="menuitem" data-testid="fact-held-by" @click="startHolding"></v-list-item>
                <v-divider></v-divider>
                <v-list-item prepend-icon="mdi-pencil" title="Edit" role="menuitem" data-testid="fact-edit" @click="emitClose('edit')"></v-list-item>
                <v-list-item prepend-icon="mdi-calendar-edit" title="Change dates" role="menuitem" data-testid="fact-dates" @click="emitClose('dates')"></v-list-item>
                <v-list-item
                    prepend-icon="mdi-timer-off-outline"
                    title="End this"
                    :subtitle="draft ? 'not on a draft' : undefined"
                    role="menuitem"
                    data-testid="fact-end"
                    :disabled="draft || !!fact.valid_until"
                    @click="emitClose('end')"
                ></v-list-item>
                <v-list-item prepend-icon="mdi-delete-outline" title="Remove" role="menuitem" data-testid="fact-remove" @click="emitClose('remove')"></v-list-item>
                <v-divider></v-divider>
                <!-- the browser's own, as a text box has them; a fact row
                     isn't edited in place, so only Copy and Select all do
                     anything here -->
                <v-list-item prepend-icon="mdi-content-cut" title="Cut" role="menuitem" disabled></v-list-item>
                <v-list-item prepend-icon="mdi-content-copy" title="Copy" role="menuitem" @click="copyText"></v-list-item>
                <v-list-item prepend-icon="mdi-content-paste" title="Paste" role="menuitem" disabled></v-list-item>
                <v-list-item prepend-icon="mdi-select-all" title="Select all" role="menuitem" @click="selectAll"></v-list-item>
                <v-list-item prepend-icon="mdi-undo" title="Undo" role="menuitem" disabled></v-list-item>
                <v-list-item prepend-icon="mdi-redo" title="Redo" role="menuitem" disabled></v-list-item>
                <v-divider></v-divider>
                <div class="px-4 py-2 text-caption text-muted" data-testid="spell-check-hint">Spell check: Shift+right-click</div>
            </v-list>
        </v-card>

        <!-- Move to… / Copy to…: the entry search -->
        <v-card
            v-else-if="mode === 'move' || mode === 'copy'"
            class="pa-3"
            min-width="300"
            :data-testid="mode === 'move' ? 'fact-move-menu' : 'fact-copy-menu'"
            @keydown.esc="escape($event)"
        >
            <div class="text-caption text-muted mb-2">{{ mode === 'move' ? moveNote : copyNote }}</div>
            <v-autocomplete
                v-model="target"
                :items="targets"
                item-title="name"
                item-value="id"
                :label="mode === 'move' ? 'Move to' : 'Copy to'"
                density="compact"
                variant="outlined"
                hide-details
                autofocus
                :data-testid="mode === 'move' ? 'move-target' : 'copy-target'"
            >
                <template #item="{ props: itemProps, item }">
                    <v-list-item v-bind="itemProps" :subtitle="item.raw.stub ? `${item.raw.kind} · stub` : item.raw.kind"></v-list-item>
                </template>
            </v-autocomplete>
            <div class="d-flex ga-2 mt-3">
                <v-btn
                    color="accent"
                    variant="flat"
                    size="small"
                    :disabled="!target"
                    :loading="!!worlds.pending[mode === 'move' ? 'move_fact' : 'copy_fact']"
                    @click="send(mode)"
                >{{ mode === 'move' ? 'Move' : 'Copy' }}</v-btn>
                <v-btn variant="text" size="small" @click="open = false">Cancel</v-btn>
            </div>
        </v-card>

        <!-- Held by… -->
        <v-card v-else class="pa-3" min-width="300" data-testid="fact-held-menu" @keydown.esc="escape($event)">
            <div class="text-caption text-muted mb-2">A belief someone holds rather than the world's truth: in a scene, the faithful speak of it as fact, but the narration doesn't confirm it.</div>
            <v-autocomplete
                v-model="holder"
                :items="holders"
                item-title="name"
                item-value="id"
                label="Held by"
                density="compact"
                variant="outlined"
                hide-details
                autofocus
                data-testid="held-by-picker"
            ></v-autocomplete>
            <div class="d-flex ga-2 mt-3">
                <v-btn color="accent" variant="flat" size="small" :disabled="!holder" :loading="!!worlds.pending.set_held_by" @click="setHolder(holder)">Save</v-btn>
                <v-btn v-if="heldBy" variant="outlined" size="small" :disabled="!!worlds.pending.set_held_by" @click="setHolder(null)">Clear</v-btn>
                <v-btn variant="text" size="small" @click="open = false">Cancel</v-btn>
            </div>
        </v-card>
    </v-menu>
    </span>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { escapeCloses } from './worldKinds.js';

// A fact's menu (spec "Menus that work everywhere"), on its "⋯" or a
// right-click on its row (one with no words selected: those get the
// selection menu):
// - "Move to… 🔎" (the fact moves onto another entry: `move_fact`, copied
//   with a new id and removed here, one revision), "Copy to… 🔎"
//   (`copy_fact`, kept here too) and "Held by… 🔎" (any other entry holds
//   it as a belief, `set_held_by`; Clear makes it the world's truth);
// - Edit, Change dates, End this and Remove, emitted (`edit`, `dates`,
//   `end`, `remove`) for the page to open its form or remove it;
// - and the browser's own items as a text box has them, with the
//   spell-check hint.
// On a draft (`draft`) nothing is written: Move, Copy and Held by are
// emitted (`move`, `copy` with the entry picked, `held` with the holder
// or null) for the draft to change, and End this is off (a draft's fact
// has no end yet). Esc closes it (once a picker's list is shut).
export default {
    name: 'FactRowActions',
    props: {
        // the fact row (`{fact_id, held_by, valid_until}`, or a draft's)
        fact: { type: Object, required: true },
        draft: { type: Boolean, default: false },
        // ids never offered (the page's own entry)
        exclude: { type: Array, default: () => [] },
    },
    emits: ['edit', 'dates', 'end', 'remove', 'move', 'copy', 'held'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { open: false, mode: 'list', point: null, target: null, holder: null, row: null };
    },
    computed: {
        excluded() {
            return [...this.exclude, this.worlds.selectedThingId].filter(Boolean);
        },
        // every entry and live stub but the page's own
        targets() {
            return this.worlds.referenceTargets.filter((target) => !this.excluded.includes(target.id));
        },
        // every other entry (not a stub): any live entry may hold a belief
        holders() {
            return this.worlds.referenceTargets.filter((target) => !target.stub && !this.excluded.includes(target.id));
        },
        heldBy() {
            return this.draft ? this.fact.held_by : this.fact.held_by?.id;
        },
        moveNote() {
            return this.draft
                ? 'Make this a fact for another page: it\'s written there on Accept, not here.'
                : 'Move this fact onto the entry it\'s about. It leaves this page.';
        },
        copyNote() {
            return this.draft ? 'Write this fact on another page too, on Accept.' : 'Copy this fact onto another entry. It stays here too.';
        },
    },
    mounted() {
        // a right-click anywhere on the row opens the menu there
        this.row = this.$refs.anchor?.closest('.fact-host') || null;
        this.row?.addEventListener('contextmenu', this.onContext);
    },
    beforeUnmount() {
        this.row?.removeEventListener('contextmenu', this.onContext);
    },
    methods: {
        // open on the list (`point`: where a right-click was, else the ⋯)
        show(point) {
            this.mode = 'list';
            this.point = point;
            this.target = null;
        },
        onContext(event) {
            if (event.defaultPrevented) {
                return;
            }
            event.preventDefault();
            this.show([event.clientX, event.clientY]);
            this.open = true;
        },
        // Esc closes the menu, unless it closes its picker's list first
        escape(event) {
            if (escapeCloses(event)) {
                this.open = false;
            }
        },
        emitClose(action) {
            this.open = false;
            this.$emit(action);
        },
        startHolding() {
            this.holder = this.heldBy || null;
            this.mode = 'held';
        },
        send(mode) {
            const target = this.worlds.referenceTargets.find((item) => item.id === this.target);
            if (!target) {
                return;
            }
            if (this.draft) {
                this.$emit(mode, target);
            } else if (mode === 'move') {
                this.worlds.moveFact(this.fact.fact_id, target.id);
            } else {
                this.worlds.copyFact(this.fact.fact_id, target.id);
            }
            this.open = false;
        },
        setHolder(id) {
            if (this.draft) {
                const holder = id ? this.worlds.referenceTargets.find((item) => item.id === id) : null;
                this.$emit('held', holder ? { id: holder.id, name: holder.name } : null);
            } else {
                this.worlds.setHeldBy(this.fact.fact_id, id);
            }
            this.open = false;
        },
        // the row's words, for Copy and Select all
        textElement() {
            return this.row?.querySelector('.fact-text') || null;
        },
        copyText() {
            const selected = window.getSelection()?.toString();
            const text = selected || this.textElement()?.textContent || '';
            navigator.clipboard?.writeText(text).catch(() => {});
            this.open = false;
        },
        selectAll() {
            const element = this.textElement();
            if (element) {
                const range = document.createRange();
                range.selectNodeContents(element);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
            }
            this.open = false;
        },
    },
};
</script>

<style scoped>
.fact-menu-anchor {
    flex: none;
}

.fact-menu {
    background: rgb(var(--v-theme-raised));
}
</style>
