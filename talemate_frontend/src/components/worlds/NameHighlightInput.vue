<template>
    <div class="name-input">
        <label v-if="label && showLabel" :for="inputId" class="input-label">{{ label }}</label>
        <div class="prompt-box" @contextmenu="openMenu">
            <textarea
                :id="inputId"
                ref="input"
                :value="modelValue"
                class="prompt-input"
                :class="{ dense }"
                :aria-label="label"
                :rows="rows"
                :placeholder="placeholder"
                :disabled="disabled"
                @input="onInput"
            ></textarea>
            <div class="prompt-layer" :class="{ dense }" aria-hidden="true">
                <template v-for="segment in segments" :key="segment.start">
                    <mark
                        v-if="!pickable && (segment.match || segment.ref)"
                        class="name"
                        :class="segment.state"
                        data-testid="name-match"
                        @mousedown.prevent="caretAt(segment.end)"
                    >{{ segment.text }}</mark>
                    <v-menu v-else-if="segment.match || segment.ref" open-on-hover location="bottom start" :open-delay="100">
                        <template #activator="{ props }">
                            <mark
                                v-bind="props"
                                class="name"
                                :class="segment.state"
                                data-testid="name-match"
                                @mousedown.prevent="caretAt(segment.end)"
                            >{{ segment.text }}</mark>
                        </template>
                        <v-list density="compact" class="name-popover" data-testid="name-popover">
                            <v-list-subheader v-if="segment.state === 'suggested'">Did you mean…</v-list-subheader>
                            <v-list-item
                                v-for="candidate in choicesOf(segment)"
                                :key="candidate.id"
                                :active="chosenId(segment) === candidate.id"
                                :aria-selected="String(chosenId(segment) === candidate.id)"
                                color="highlight1"
                                data-testid="name-candidate"
                                @click="pick(segment, candidate.id)"
                            >
                                <template #prepend>
                                    <v-icon size="small">{{ chosenId(segment) === candidate.id ? 'mdi-check' : 'mdi-blank' }}</v-icon>
                                </template>
                                <v-list-item-title>{{ candidate.name }}</v-list-item-title>
                                <v-list-item-subtitle>{{ candidate.kind }}{{ candidate.stub ? ' · stub' : '' }}</v-list-item-subtitle>
                            </v-list-item>
                            <v-divider></v-divider>
                            <v-list-item
                                :active="chosenId(segment) === NEW_THING && segment.state !== 'suggested'"
                                color="warning"
                                prepend-icon="mdi-pencil"
                                @click="pick(segment, NEW_THING)"
                            >
                                <v-list-item-title>Treat as new</v-list-item-title>
                            </v-list-item>
                        </v-list>
                    </v-menu>
                    <v-menu v-else-if="segment.unknown" open-on-hover location="bottom start" :open-delay="100">
                        <template #activator="{ props }">
                            <mark
                                v-bind="props"
                                class="name"
                                :class="segment.state"
                                data-testid="name-unknown"
                                @mousedown.prevent="caretAt(segment.end)"
                            >{{ segment.text }}</mark>
                        </template>
                        <v-list density="compact" class="name-popover" data-testid="unknown-popover">
                            <template v-if="segment.state === 'stub'">
                                <v-list-subheader>Made a {{ stubKindOf(segment) }} stub on save</v-list-subheader>
                                <v-list-item prepend-icon="mdi-close" title="Don't make a stub" @click="unstub(segment)"></v-list-item>
                            </template>
                            <template v-else>
                                <v-list-subheader>Not a world name yet. Make a stub:</v-list-subheader>
                                <v-list-item
                                    v-for="kind in stubKinds"
                                    :key="kind.value"
                                    :title="kind.title"
                                    data-testid="stub-kind-option"
                                    @click="makeStub(segment, kind.value)"
                                ></v-list-item>
                            </template>
                        </v-list>
                    </v-menu>
                    <mark v-else-if="segment.state" class="name new" data-testid="name-new">{{ segment.text }}</mark>
                    <template v-else>{{ segment.text }}</template>
                </template>&#8203;
            </div>
        </div>
        <ReferenceMenu
            v-model="menuOpen"
            :target="menuTarget"
            :has-selection="selection[1] > selection[0]"
            :exclude="exclude"
            @cut="cut"
            @copy="copy"
            @paste="paste"
            @delete="deleteSelection"
            @undo="undo"
            @redo="redo"
            @select-all="selectAll"
            @pick="addReference"
        />
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { NEW_THING, pickKey, pickedId, promptSegments } from './nameHighlights.js';
import { STUB_KINDS, kindInfo } from './worldKinds.js';
import ReferenceMenu from './ReferenceMenu.vue';

let nextId = 0;

// A text box the owner writes names in (the new-scene prompt, the create
// box's prompt, the fact form), with the world thing names in it
// highlighted as they type (`match_names`, looked up once typing rests,
// as of `at`):
// - a matched name is solid, and its hover popover re-picks the thing or
//   treats the name as new (`picks`: pickKey -> thing id or NEW_THING);
// - a suggested (partial) match is dotted, its popover asking "Did you
//   mean…";
// - with `offerStubs`, an unknown capitalised phrase is dotted too, and its
//   popover offers to make it a stub of a kind (`stubs`, `[{text, kind}]`;
//   the owner of the box makes them);
// - `invented` names (the last scene setup's) show as new;
// - an edited fact's existing links (`linked`, `locateLinks` spans) show
//   as matched to their own things, whatever the name would match; a
//   re-pick or "treat as new" in their popover changes that link alone
//   (`pick-link {index, id}`), never the other words like it.
// Right-clicking opens `ReferenceMenu`: Cut, Copy, Paste, Delete, Undo,
// Redo, Select all, and Add reference…, which inserts the thing's name at
// the cursor and records a reference for it (`refs`: pickKey ->
// `{id, text}`), so it links there. Shift+right-click skips the custom
// menu for the browser's own (its spell-check, which scripts can't see).
// Cut/Copy/Paste/Delete/Undo/Redo run as the textarea's own editing
// commands (`execCommand`, deprecated but still the only way to reach its
// native undo history), so they land on that history and a later Undo (or
// Ctrl+Z) can revert them; `syncFromInput` brings the model back in step
// when the command changed the value without firing its own `input`.
//
// The highlights are a layer over the textarea, in the same font and box,
// with transparent text: only the marks show (and take the hover).
export default {
    name: 'NameHighlightInput',
    components: { ReferenceMenu },
    props: {
        modelValue: { type: String, default: '' },
        picks: { type: Object, default: () => ({}) },
        refs: { type: Object, default: () => ({}) },
        stubs: { type: Array, default: () => [] },
        // the date the names are as of (null for the latest)
        at: { type: Object, default: null },
        label: { type: String, default: '' },
        // the label shows above the box (else it only names it)
        showLabel: { type: Boolean, default: true },
        placeholder: { type: String, default: '' },
        rows: { type: [Number, String], default: 3 },
        dense: { type: Boolean, default: false },
        disabled: { type: Boolean, default: false },
        invented: { type: Array, default: () => [] },
        // `[{start, end, ref: {id, text}}]`: links kept by position
        linked: { type: Array, default: () => [] },
        offerStubs: { type: Boolean, default: false },
        // thing ids Add reference never offers
        exclude: { type: Array, default: () => [] },
        // how long typing rests before the names are looked up
        debounce: { type: Number, default: 300 },
        autofocus: { type: Boolean, default: false },
        // false where the box's request takes no picks: names highlight,
        // with no menu to re-pick them
        pickable: { type: Boolean, default: true },
    },
    emits: ['update:modelValue', 'update:picks', 'update:refs', 'update:stubs', 'pick-link'],
    setup() {
        return { worlds: useWorldsStore(), NEW_THING };
    },
    data() {
        nextId += 1;
        return {
            inputId: `name-input-${nextId}`,
            matchTimer: null,
            menuOpen: false,
            menuTarget: null,
            // the textarea's selection when the menu opened
            selection: [0, 0],
        };
    },
    computed: {
        matches() {
            return this.worlds.matchesFor(this.modelValue, this.at);
        },
        unknown() {
            return this.offerStubs ? this.worlds.unknownFor(this.modelValue, this.at) : [];
        },
        segments() {
            return promptSegments(this.modelValue, this.matches, this.picks, this.invented, {
                refs: this.refs,
                unknown: this.unknown,
                stubs: this.stubs,
                linked: this.linked,
            });
        },
        stubKinds() {
            return STUB_KINDS.map((kind) => ({ title: kindInfo(kind)?.singular || kind, value: kind }));
        },
    },
    watch: {
        modelValue() {
            this.scheduleMatch();
            this.$nextTick(this.grow);
        },
        at() {
            this.scheduleMatch();
        },
    },
    mounted() {
        if (this.modelValue.trim()) {
            this.scheduleMatch();
        }
        this.$nextTick(this.grow);
        // shown again, or its column resized (an error message above it,
        // a world switched while hidden): measure again (polish 5)
        if (typeof ResizeObserver !== 'undefined') {
            this.resizer = new ResizeObserver(() => this.grow());
            this.resizer.observe(this.$el);
        }
        if (this.autofocus) {
            this.$nextTick(this.focus);
        }
    },
    beforeUnmount() {
        clearTimeout(this.matchTimer);
        this.resizer?.disconnect();
        this.worlds.dropNameBox(this.inputId);
    },
    methods: {
        focus() {
            this.$refs.input?.focus();
        },
        scheduleMatch() {
            clearTimeout(this.matchTimer);
            this.matchTimer = setTimeout(() => this.worlds.matchNames(this.modelValue, this.at, this.inputId), this.debounce);
        },
        onInput(event) {
            this.$emit('update:modelValue', event.target.value);
            this.grow();
        },
        grow() {
            const input = this.$refs.input;
            if (input) {
                input.style.height = 'auto';
                input.style.height = `${input.scrollHeight + 2}px`;
            }
        },
        caretAt(offset) {
            const input = this.$refs.input;
            if (input) {
                input.focus();
                input.setSelectionRange(offset, offset);
            }
        },
        // --- matched names ------------------------------------------------
        // the things a highlighted name can be: its candidates, and the
        // thing a reference made by hand points at
        choicesOf(segment) {
            const choices = segment.match ? [...segment.match.candidates] : [];
            const ref = segment.ref || this.refs[pickKey(segment.text)];
            // a link's thing, and the one it had when the form opened
            for (const id of [ref?.id, ref?.was]) {
                if (id && id !== NEW_THING && !choices.some((choice) => choice.id === id)) {
                    const target = this.worlds.referenceTargets.find((t) => t.id === id);
                    choices.unshift({ id, name: target?.name || ref.text, kind: target?.kind || '', stub: !!target?.stub });
                }
            }
            return choices;
        },
        chosenId(segment) {
            if (segment.linked) {
                return segment.ref.id;
            }
            if (segment.match) {
                return pickedId(segment.match, this.picks, this.refs);
            }
            return this.picks[pickKey(segment.text)] === NEW_THING ? NEW_THING : segment.ref?.id;
        },
        pick(segment, id) {
            const key = pickKey(segment.text);
            if (segment.linked) {
                this.$emit('pick-link', { index: segment.linkIndex, id });
                return;
            }
            if (!segment.match && id === NEW_THING) {
                // a reference with no match behind it: just dropped
                const { [key]: _gone, ...refs } = this.refs;
                this.$emit('update:refs', refs);
                return;
            }
            this.$emit('update:picks', { ...this.picks, [key]: id });
        },
        // --- unknown phrases ----------------------------------------------
        makeStub(segment, kind) {
            this.$emit('update:stubs', [...this.stubs.filter((s) => pickKey(s.text) !== pickKey(segment.text)), { text: segment.text, kind }]);
        },
        unstub(segment) {
            this.$emit('update:stubs', this.stubs.filter((s) => pickKey(s.text) !== pickKey(segment.text)));
        },
        stubKindOf(segment) {
            const kind = this.stubs.find((s) => pickKey(s.text) === pickKey(segment.text))?.kind;
            return kindInfo(kind)?.singular || kind;
        },
        // --- the right-click menu -----------------------------------------
        openMenu(event) {
            if (this.disabled) {
                return;
            }
            if (event.shiftKey) {
                // the owner's way to the browser's own menu (spell-check)
                return;
            }
            event.preventDefault();
            const input = this.$refs.input;
            this.selection = input ? [input.selectionStart, input.selectionEnd] : [this.modelValue.length, this.modelValue.length];
            this.menuTarget = [event.clientX, event.clientY];
            this.menuOpen = true;
        },
        // `text` in place of the selection the menu opened with, the caret
        // after it
        insertAt(text) {
            const [start, end] = this.selection;
            const value = this.modelValue.slice(0, start) + text + this.modelValue.slice(end);
            this.$emit('update:modelValue', value);
            this.$nextTick(() => this.caretAt(start + text.length));
        },
        selectedText() {
            return this.modelValue.slice(this.selection[0], this.selection[1]);
        },
        // focuses the textarea and restores the selection the menu opened
        // with (the click on a menu item may have moved focus off it)
        focusSelection() {
            const input = this.$refs.input;
            if (!input) {
                return null;
            }
            input.focus();
            input.setSelectionRange(this.selection[0], this.selection[1]);
            return input;
        },
        // after an execCommand that may have changed the textarea's value
        // without firing its own `input` event: bring the model into step
        syncFromInput(input) {
            if (input && input.value !== this.modelValue) {
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        },
        cut() {
            const input = this.focusSelection();
            document.execCommand('cut');
            this.syncFromInput(input);
        },
        copy() {
            this.focusSelection();
            document.execCommand('copy');
        },
        paste() {
            navigator.clipboard
                ?.readText()
                .then((text) => {
                    const input = this.focusSelection();
                    document.execCommand('insertText', false, text);
                    this.syncFromInput(input);
                })
                .catch(() => {});
        },
        deleteSelection() {
            const input = this.focusSelection();
            document.execCommand('delete');
            this.syncFromInput(input);
        },
        selectAll() {
            this.$refs.input?.select();
        },
        undo() {
            const input = this.$refs.input;
            input?.focus();
            document.execCommand('undo');
            this.syncFromInput(input);
        },
        redo() {
            const input = this.$refs.input;
            input?.focus();
            document.execCommand('redo');
            this.syncFromInput(input);
        },
        // the thing's name goes in at the cursor, linked to it
        addReference(target) {
            const key = pickKey(target.name);
            this.insertAt(target.name);
            this.$emit('update:refs', { ...this.refs, [key]: { id: target.id, text: target.name } });
            if (key in this.picks) {
                const { [key]: _old, ...picks } = this.picks;
                this.$emit('update:picks', picks);
            }
        },
    },
};
</script>

<style scoped>
.input-label {
    display: block;
    font-size: 12px;
    margin-bottom: 2px;
    color: rgb(var(--v-theme-muted));
}

.prompt-box {
    position: relative;
}

/* the textarea and the highlight layer share one box, font and wrapping */
.prompt-input,
.prompt-layer {
    font: inherit;
    font-size: 14px;
    line-height: 1.7;
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 4px;
    white-space: pre-wrap;
    overflow-wrap: break-word;
    word-break: normal;
    letter-spacing: normal;
}

.prompt-input.dense,
.prompt-layer.dense {
    padding: 5px 8px;
}

.prompt-input {
    display: block;
    width: 100%;
    resize: none;
    overflow: hidden;
    color: rgb(var(--v-theme-on-surface));
    background: rgb(var(--v-theme-background));
    border-color: rgb(var(--v-theme-border));
    outline: none;
}

.prompt-input:focus {
    border-color: rgb(var(--v-theme-accent));
}

.prompt-input:disabled {
    opacity: 0.6;
}

.prompt-layer {
    position: absolute;
    inset: 0;
    color: transparent;
    pointer-events: none;
    overflow: hidden;
}

.name {
    color: transparent;
    border-radius: 2px;
    pointer-events: auto;
    cursor: pointer;
}

.name.matched {
    background: rgba(var(--v-theme-highlight1), 0.25);
    border-bottom: 2px solid rgb(var(--v-theme-highlight1));
}

.name.new,
.name.stub {
    background: rgba(var(--v-theme-warning), 0.2);
    border-bottom: 2px solid rgb(var(--v-theme-warning));
}

.name.suggested {
    background: transparent;
    border-bottom: 2px dotted rgb(var(--v-theme-highlight1));
}

.name.unknown {
    background: transparent;
    border-bottom: 2px dotted rgb(var(--v-theme-muted));
}

.name-popover {
    min-width: 220px;
}
</style>
