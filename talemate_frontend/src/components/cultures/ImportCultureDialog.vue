<template>
    <v-dialog v-model="localOpen" max-width="560px">
        <v-card>
            <v-card-title class="d-flex align-center ga-2">
                <v-icon color="primary">mdi-file-upload-outline</v-icon>
                Import culture
            </v-card-title>
            <v-card-text>
                <v-file-input
                    v-model="selectedFile"
                    label="Culture file (.json)"
                    accept=".json"
                    density="compact"
                    variant="outlined"
                    prepend-icon="mdi-paperclip"
                    show-size
                    hide-details
                    class="mb-3"
                    @update:model-value="onFileChange"
                ></v-file-input>

                <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">
                    {{ error }}
                </v-alert>

                <div v-if="previewLoading" class="d-flex justify-center pa-4">
                    <v-progress-circular indeterminate color="primary"></v-progress-circular>
                </div>

                <template v-if="preview">
                    <v-card variant="tonal" class="pa-3 mb-3">
                        <div class="d-flex align-center ga-2 flex-wrap mb-2">
                            <span class="text-h6 font-weight-regular">{{ preview.culture_name }}</span>
                            <v-chip size="small" :color="preview.is_update ? 'amber' : 'green'" variant="tonal">
                                {{ preview.is_update ? 'Updating' : 'New' }}
                            </v-chip>
                        </div>
                        <div class="d-flex flex-wrap ga-6">
                            <div v-for="stat in statEntries" :key="stat.label">
                                <div class="text-h6 font-weight-regular">{{ stat.value }}</div>
                                <div class="text-caption text-muted">{{ stat.label }}</div>
                            </div>
                        </div>
                    </v-card>

                    <div class="d-flex flex-column ga-2">
                        <div class="d-flex ga-2 align-start">
                            <v-icon size="small" :color="preview.name_clash ? 'warning' : 'green'">
                                {{ preview.name_clash ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline' }}
                            </v-icon>
                            <span v-if="preview.name_clash">
                                Another culture ({{ preview.name_clash }}) already uses the name "{{ preview.culture_name }}".
                            </span>
                            <span v-else>
                                {{ preview.is_update ? 'Updating the existing culture, ' : 'New culture, ' }}no name clash.
                            </span>
                        </div>

                        <div v-if="preview.claimed_unassigned.length" class="d-flex ga-2 align-start">
                            <v-icon size="small" color="amber">mdi-link-variant</v-icon>
                            <span>
                                Claims {{ preview.claimed_unassigned.length }}
                                name{{ preview.claimed_unassigned.length === 1 ? '' : 's' }} from Unassigned names:
                                {{ preview.claimed_unassigned.join(', ') }}.
                            </span>
                        </div>

                        <div v-if="preview.places_existing.length || preview.places_new.length" class="d-flex ga-2 align-start">
                            <v-icon size="small" color="teal">mdi-map-marker-outline</v-icon>
                            <span>
                                {{ preview.places_existing.length }} existing
                                place{{ preview.places_existing.length === 1 ? '' : 's' }},
                                {{ preview.places_new.length }} new
                                place{{ preview.places_new.length === 1 ? '' : 's' }}.
                            </span>
                        </div>

                        <div v-if="preview.conflicts.length" class="d-flex ga-2 align-start">
                            <v-icon size="small" color="amber">mdi-shield-alert-outline</v-icon>
                            <span>
                                {{ preview.conflicts.length }} glossary
                                entr{{ preview.conflicts.length === 1 ? 'y' : 'ies' }} kept from Talemate
                                (reviewed or edited): {{ preview.conflicts.join(', ') }}.
                            </span>
                        </div>

                        <div v-for="warning in preview.warnings" :key="warning" class="d-flex ga-2 align-start">
                            <v-icon size="small" color="muted">mdi-information-outline</v-icon>
                            <span>{{ warning }}</span>
                        </div>

                        <div class="d-flex ga-2 align-start">
                            <v-icon size="small" color="muted">mdi-earth</v-icon>
                            <span>Saved to the linked shared world, available in every scene.</span>
                        </div>
                    </div>
                </template>
            </v-card-text>
            <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn variant="text" @click="close()">Cancel</v-btn>
                <v-btn
                    color="primary"
                    variant="flat"
                    prepend-icon="mdi-download"
                    :disabled="!preview || previewLoading"
                    :loading="applying"
                    @click="applyImport()"
                >
                    Import {{ preview ? preview.culture_name : '' }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { v4 as uuidv4 } from 'uuid';

export default {
    name: 'ImportCultureDialog',
    inject: [
        'registerMessageHandler',
        'unregisterMessageHandler',
    ],
    props: {
        modelValue: {
            type: Boolean,
            default: false,
        },
        send: {
            type: Function,
            required: true,
        },
    },
    emits: [
        'update:modelValue',
    ],
    data() {
        return {
            selectedFile: null,
            pendingContent: null,
            // request_id of our outstanding preview/apply, echoed back by
            // the backend in an error reply
            pendingRequestId: null,
            preview: null,
            error: null,
            previewLoading: false,
            applying: false,
        }
    },
    computed: {
        localOpen: {
            get() {
                return this.modelValue;
            },
            set(value) {
                this.$emit('update:modelValue', value);
            },
        },
        statEntries() {
            if (!this.preview) {
                return [];
            }
            const labels = {
                words: 'words',
                phrases: 'phrases',
                generators: 'generators',
                glossary: 'glossary names',
                places: 'places',
            };
            return Object.entries(this.preview.counts || {}).map(([key, value]) => ({
                label: labels[key] || key,
                value,
            }));
        },
    },
    watch: {
        // Covers both the dialog's own close() (sets modelValue false via
        // localOpen) and it being opened programmatically by the parent
        // (openImport(), from the drawer or "Re-import"), which only
        // changes the `modelValue` prop and never goes through the
        // `localOpen` setter above.
        modelValue(value) {
            if (value) {
                // Opening fresh: don't carry over a stale error from
                // whatever was last shown here, including one that turned
                // out to belong to an unrelated request (see handleMessage's
                // own `previewLoading || applying` gate).
                this.error = null;
            } else {
                this.resetState();
            }
        },
    },
    methods: {
        onFileChange(value) {
            const file = Array.isArray(value) ? value[0] : value;
            this.error = null;
            this.preview = null;
            this.pendingContent = null;
            if (!file) {
                return;
            }

            this.previewLoading = true;
            const reader = new FileReader();
            reader.onload = () => {
                this.pendingContent = reader.result;
                this.pendingRequestId = uuidv4();
                this.send('import_preview', { content: this.pendingContent, request_id: this.pendingRequestId });
            };
            reader.onerror = () => {
                this.previewLoading = false;
                this.error = 'Could not read the file.';
            };
            reader.readAsText(file);
        },
        applyImport() {
            if (!this.pendingContent || this.applying) {
                return;
            }
            this.error = null;
            this.applying = true;
            this.pendingRequestId = uuidv4();
            this.send('import_apply', { content: this.pendingContent, request_id: this.pendingRequestId });
        },
        resetState() {
            this.selectedFile = null;
            this.pendingContent = null;
            this.pendingRequestId = null;
            this.preview = null;
            this.error = null;
            this.previewLoading = false;
            this.applying = false;
        },
        close() {
            this.localOpen = false;
        },
        handleMessage(message) {
            if (message.type !== 'cultures') {
                return;
            }
            if (message.action === 'import_preview') {
                this.previewLoading = false;
                this.preview = message.data;
            } else if (message.action === 'operation_done') {
                if (message.error) {
                    // This dialog is mounted for the lifetime of the page, so
                    // without this guard it would also pick up unrelated
                    // failures (a rejected save_place reparent, a failed
                    // glossary save, ...) and show them as an import error.
                    // Only accept one while we actually have a preview or
                    // apply request of our own outstanding.
                    if (!this.previewLoading && !this.applying) {
                        return;
                    }
                    // Import errors carry our request_id; an error tagged
                    // with some other request (a failed roll) isn't ours.
                    // Untagged errors are still accepted, so a failure the
                    // backend couldn't tag never leaves the spinner running.
                    const requestId = message.error.request_id;
                    if (requestId && requestId !== this.pendingRequestId) {
                        return;
                    }
                    this.previewLoading = false;
                    this.applying = false;
                    this.error = message.error.message;
                } else if (this.applying) {
                    this.applying = false;
                    this.close();
                }
            }
        },
    },
    mounted() {
        this.registerMessageHandler(this.handleMessage);
    },
    unmounted() {
        this.unregisterMessageHandler(this.handleMessage);
    },
}
</script>
