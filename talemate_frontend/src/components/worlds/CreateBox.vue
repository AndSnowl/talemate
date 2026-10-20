<template>
    <v-card variant="flat" class="create-box pa-3 mb-4" data-testid="create-box">
        <div class="text-subtitle-2 mb-1">New {{ info.singular }}</div>
        <v-textarea
            v-model="prompt"
            label="Describe it"
            :placeholder="placeholder"
            rows="2"
            auto-grow
            density="compact"
            variant="outlined"
            hide-details
            :disabled="busy"
        ></v-textarea>

        <div class="d-flex align-center flex-wrap ga-2 mt-2">
            <v-text-field
                v-if="kind === 'character'"
                v-model.number="bornYear"
                label="Born (year)"
                type="number"
                min="1"
                max="9999"
                density="compact"
                variant="outlined"
                hide-details
                class="picker"
                :disabled="busy"
            ></v-text-field>
            <v-select
                v-if="kind === 'place'"
                v-model="parentId"
                label="Inside (place)"
                :items="parentOptions"
                item-title="name"
                item-value="id"
                clearable
                density="compact"
                variant="outlined"
                hide-details
                class="picker picker-wide"
                :disabled="busy"
            ></v-select>
            <v-spacer></v-spacer>
            <v-btn
                color="accent"
                variant="flat"
                size="small"
                prepend-icon="mdi-creation"
                :loading="worlds.previewPending && mine"
                :disabled="!prompt.trim() || busy || !validBorn"
                @click="create"
            >Create</v-btn>
        </div>
        <div class="text-caption text-muted mt-1">
            Pickers are optional; the AI fills in the rest from your description.
        </div>

        <v-alert v-if="mine && worlds.previewError" type="error" variant="tonal" density="compact" class="mt-3">
            {{ worlds.previewError }}
        </v-alert>

        <v-card v-if="preview" variant="tonal" class="preview mt-3 pa-3" data-testid="create-preview">
            <div class="d-flex align-center ga-2 mb-2">
                <v-text-field
                    v-model="previewName"
                    label="Name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="preview-name"
                ></v-text-field>
                <span v-if="preview.fields.born" class="text-caption text-muted">
                    born <span class="world-date">{{ formatDate(worlds.calendar, preview.fields.born) }}</span>
                </span>
            </div>

            <div v-for="(text, section) in preview.prose" :key="section" class="mb-2">
                <div class="text-caption text-muted text-uppercase">{{ section }}</div>
                <div class="prose">{{ text }}</div>
            </div>

            <div class="text-caption text-muted text-uppercase mt-2">Facts</div>
            <div v-for="(fact, index) in preview.facts" :key="index" class="fact d-flex align-center ga-2">
                <span class="flex-grow-1">{{ fact.text }}</span>
                <v-chip size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
                <span class="fact-date">{{ fact.since ? formatDate(worlds.calendar, fact.since) + ' →' : 'always' }}</span>
            </div>

            <div class="d-flex ga-2 mt-3">
                <v-btn
                    color="accent"
                    variant="flat"
                    size="small"
                    prepend-icon="mdi-check"
                    :loading="!!worlds.pending.accept_preview"
                    :disabled="!previewName.trim()"
                    @click="accept"
                >Accept</v-btn>
                <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" :disabled="!!worlds.pending.accept_preview" @click="worlds.regeneratePreview()">Regenerate</v-btn>
                <v-btn variant="outlined" size="small" prepend-icon="mdi-pencil" :disabled="!!worlds.pending.accept_preview" @click="worlds.discardPreview()">Edit</v-btn>
            </div>
        </v-card>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, formatDate } from './worldDates.js';
import { kindInfo } from './worldKinds.js';

const PLACEHOLDERS = {
    character: 'A grizzled ferryman who owes the Wardens more than money…',
    place: 'A half-flooded market town on the river, a little shady…',
    lore: 'The old treaty that sets the river tolls…',
};

// The "describe it, then create" box for one kind: a prompt plus the
// optional core-field pickers (born for characters, the parent place for
// places). Create shows the backend's preview, which can be accepted,
// regenerated, or dropped to edit the prompt and try again.
export default {
    name: 'CreateBox',
    props: {
        kind: { type: String, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            prompt: '',
            bornYear: null,
            parentId: null,
            previewName: '',
        };
    },
    computed: {
        info() {
            return kindInfo(this.kind);
        },
        placeholder() {
            return PLACEHOLDERS[this.kind] || '';
        },
        parentOptions() {
            return this.worlds.things.place || [];
        },
        // the store's preview request is this box's
        mine() {
            return this.worlds.previewRequest?.kind === this.kind;
        },
        preview() {
            return this.mine ? this.worlds.preview : null;
        },
        busy() {
            return (this.mine && this.worlds.previewPending) || !!this.worlds.pending.accept_preview;
        },
        validBorn() {
            const year = this.bornYear;
            return year === null || year === '' || (Number.isInteger(year) && year >= 1 && year <= 9999);
        },
    },
    watch: {
        preview(preview) {
            this.previewName = preview?.name || '';
        },
        // the request is gone once its preview is accepted (or the world
        // changes): start the box afresh
        'worlds.previewRequest'(request, before) {
            if (!request && before?.kind === this.kind) {
                this.prompt = '';
                this.bornYear = null;
                this.parentId = null;
            }
        },
    },
    methods: {
        formatDate,
        fields() {
            const fields = {};
            if (this.kind === 'character' && Number.isInteger(this.bornYear)) {
                fields.born = dateOf(this.bornYear);
            }
            if (this.kind === 'place' && this.parentId) {
                fields.parent = this.parentId;
            }
            return fields;
        },
        create() {
            if (!this.prompt.trim()) {
                return;
            }
            this.worlds.previewThing(this.kind, this.prompt.trim(), this.fields());
        },
        accept() {
            this.worlds.acceptPreview({ name: this.previewName.trim() });
        },
    },
};
</script>

<style scoped>
.create-box {
    background: rgb(var(--v-theme-raised));
}

.picker {
    max-width: 160px;
}

.picker-wide {
    max-width: 260px;
}

.preview-name {
    max-width: 320px;
}

.prose {
    line-height: 1.5;
    white-space: pre-wrap;
}

.fact {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 4px 0;
}

.fact .v-chip {
    flex: none;
}

.fact-date {
    flex: none;
    font-family: monospace;
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
    min-width: 70px;
    text-align: right;
}

.world-date {
    color: rgb(var(--v-theme-date));
}
</style>
