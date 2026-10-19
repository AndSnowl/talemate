<template>
    <div class="ma-3">
        <v-row no-gutters>
            <v-col cols="12" md="3" class="pr-md-3 mb-4">
                <v-card variant="flat" color="surface" class="pa-2" style="height:100%">
                    <v-list density="compact" nav>
                        <v-list-subheader color="muted">Presets</v-list-subheader>
                        <v-list-item
                            v-for="preset in mainPresets"
                            :key="preset.id"
                            :active="activeId === preset.id"
                            color="primary"
                            @click="selectActive(preset.id)"
                        >
                            <template v-slot:prepend>
                                <div class="d-flex mr-2" style="gap:2px">
                                    <span
                                        v-for="(hex, i) in swatchesFor(preset)"
                                        :key="i"
                                        class="theme-swatch-chip"
                                        :style="{ background: hex }"
                                    ></span>
                                </div>
                            </template>
                            <v-list-item-title>{{ preset.name }}</v-list-item-title>
                        </v-list-item>

                        <v-list-subheader color="muted">Colour vision</v-list-subheader>
                        <v-list-item
                            v-for="preset in visionPresets"
                            :key="preset.id"
                            :active="activeId === preset.id"
                            color="primary"
                            @click="selectActive(preset.id)"
                        >
                            <template v-slot:prepend>
                                <div class="d-flex mr-2" style="gap:2px">
                                    <span
                                        v-for="(hex, i) in swatchesFor(preset)"
                                        :key="i"
                                        class="theme-swatch-chip"
                                        :style="{ background: hex }"
                                    ></span>
                                </div>
                            </template>
                            <v-list-item-title>{{ preset.name }}</v-list-item-title>
                        </v-list-item>

                        <v-list-subheader color="muted">Yours</v-list-subheader>
                        <v-list-item
                            v-for="theme in customThemes"
                            :key="theme.id"
                            :active="activeId === theme.id"
                            color="primary"
                            @click="selectActive(theme.id)"
                        >
                            <template v-slot:prepend>
                                <div class="d-flex mr-2" style="gap:2px">
                                    <span
                                        v-for="(hex, i) in swatchesFor(theme)"
                                        :key="i"
                                        class="theme-swatch-chip"
                                        :style="{ background: hex }"
                                    ></span>
                                </div>
                            </template>
                            <template v-if="renamingId === theme.id">
                                <v-text-field
                                    v-model="renameDraft"
                                    density="compact"
                                    variant="outlined"
                                    hide-details
                                    autofocus
                                    @click.stop
                                    @keyup.enter="commitRename(theme)"
                                    @keyup.esc="cancelRename"
                                    @blur="commitRename(theme)"
                                ></v-text-field>
                            </template>
                            <v-list-item-title v-else>{{ theme.name }}</v-list-item-title>
                            <template v-slot:append>
                                <div class="d-flex align-center" @click.stop>
                                    <v-btn icon="mdi-pencil-outline" size="x-small" variant="text" @click="startRename(theme)"></v-btn>
                                    <ConfirmActionInline
                                        icon="mdi-delete-outline"
                                        density="compact"
                                        action-label="Delete"
                                        confirm-label="Confirm delete"
                                        @confirm="deleteTheme(theme)"
                                    ></ConfirmActionInline>
                                </div>
                            </template>
                        </v-list-item>
                        <v-list-item v-if="customThemes.length === 0">
                            <v-list-item-subtitle class="text-caption text-muted">No themes of your own yet.</v-list-item-subtitle>
                        </v-list-item>
                    </v-list>
                    <v-btn
                        block
                        variant="outlined"
                        color="muted"
                        prepend-icon="mdi-content-duplicate"
                        class="mt-2"
                        @click="duplicateCurrent"
                    >Duplicate current as new</v-btn>
                </v-card>
            </v-col>

            <v-col cols="12" md="9">
                <div class="mb-3">
                    <h2 class="text-h5">{{ resolvedActive.name }}</h2>
                    <p class="text-caption text-muted mb-0">
                        Two layers, as in Doom Emacs: a palette of named colours, and roles that point at a
                        palette name. Presets set both — edit either on a theme of your own.
                    </p>
                    <v-switch
                        v-model="darkValue"
                        label="Dark theme"
                        color="primary"
                        density="compact"
                        hide-details
                        class="mt-2"
                        :disabled="!isCustomActive"
                    ></v-switch>
                </div>

                <v-card variant="flat" color="surface" class="pa-4 mb-4">
                    <div class="text-subtitle-1 mb-2">Palette</div>
                    <div class="d-flex flex-wrap" style="gap:12px">
                        <div v-for="key in paletteKeys" :key="key" class="d-flex flex-column align-center" style="width:60px;gap:4px">
                            <button
                                type="button"
                                class="theme-swatch"
                                :aria-label="'Edit ' + key"
                                :style="swatchButtonStyle(key)"
                                @click="selectedPaletteKey = key"
                            ></button>
                            <span
                                class="text-caption"
                                :style="{ color: selectedPaletteKey === key ? resolvedActive.colors['on-surface'] : resolvedActive.colors.muted }"
                            >{{ key }}</span>
                        </div>
                    </div>

                    <div class="d-flex flex-wrap align-center mt-3" style="gap:12px">
                        <span class="text-caption text-muted">Editing <code>{{ selectedPaletteKey }}</code></span>
                        <v-text-field
                            :model-value="hexDraft"
                            label="Palette colour (hex)"
                            density="compact"
                            variant="outlined"
                            hide-details
                            style="max-width:140px"
                            :disabled="!isCustomActive"
                            @update:model-value="onHexInput"
                        ></v-text-field>
                        <v-btn
                            v-if="!isCustomActive"
                            size="small"
                            variant="tonal"
                            prepend-icon="mdi-content-duplicate"
                            @click="duplicateCurrent"
                        >Duplicate to edit</v-btn>
                        <span class="text-caption text-muted">Used by: {{ usedByLabel }}</span>
                    </div>

                    <v-color-picker
                        class="mt-3"
                        mode="hex"
                        :modes="['hex']"
                        :disabled="!isCustomActive"
                        v-model="colorPickerValue"
                    ></v-color-picker>
                </v-card>

                <v-row no-gutters>
                    <v-col cols="12" md="6" class="pr-md-3 mb-4">
                        <v-card variant="flat" color="surface" class="pa-4" style="height:100%">
                            <div class="text-subtitle-1 mb-2">Roles</div>
                            <div
                                v-for="role in coreRoles"
                                :key="role.id"
                                class="d-flex align-center mb-2"
                                style="gap:10px"
                            >
                                <span class="role-swatch" :style="{ background: resolvedActive.colors[role.id] }"></span>
                                <span class="flex-grow-1 text-body-2">{{ role.label }}</span>
                                <v-select
                                    :model-value="roleValue(role.id)"
                                    :items="paletteKeys"
                                    density="compact"
                                    variant="outlined"
                                    hide-details
                                    style="max-width:150px"
                                    :disabled="!isCustomActive"
                                    @update:model-value="(v) => setRole(role.id, v)"
                                ></v-select>
                            </div>
                        </v-card>
                    </v-col>

                    <v-col cols="12" md="6" class="mb-4">
                        <v-card variant="flat" color="surface" style="overflow:hidden">
                            <div
                                class="d-flex"
                                :style="{ background: resolvedActive.colors.raised, borderBottom: '1px solid ' + resolvedActive.colors.border }"
                            >
                                <span class="theme-preview-tab" :style="{ color: resolvedActive.colors.muted }">World</span>
                                <span class="theme-preview-tab" :style="{ borderBottom: '2px solid ' + resolvedActive.colors.accent }">Story</span>
                                <span class="theme-preview-tab" :style="{ color: resolvedActive.colors.muted }">
                                    Inbox
                                    <span
                                        class="theme-preview-badge"
                                        :style="{ background: resolvedActive.colors.accent, color: resolvedActive.colors.surface }"
                                    >3</span>
                                </span>
                            </div>
                            <div class="pa-4">
                                <div class="text-caption mb-2" :style="{ color: resolvedActive.colors.date }">12 Emberwane, 412 AR &middot; evening</div>
                                <p class="mb-2" :style="{ color: resolvedActive.colors.narrator, fontStyle: 'italic' }">
                                    Snow drifts against the door of
                                    <span :style="{ color: resolvedActive.colors.link, textDecoration: 'underline dotted' }">the Gilded Ewe</span>.
                                </p>
                                <p class="mb-2">
                                    <strong :style="{ color: resolvedActive.colors.charname }">Marta:</strong>
                                    "<span :style="{ color: resolvedActive.colors.foreign, fontStyle: 'italic' }">Hael, vreda</span>, back already?"
                                </p>
                                <p class="mb-2" :style="{ color: resolvedActive.colors.narrator, fontStyle: 'italic' }">
                                    She eyes the
                                    <span :style="{ color: resolvedActive.colors.scene, textDecoration: 'underline dotted' }">gate guard</span> by the bar.
                                </p>
                                <p class="mb-3">
                                    <strong :style="{ color: resolvedActive.colors.you }">You:</strong> "I found something on the road."
                                </p>
                                <div class="d-flex flex-wrap" style="gap:8px">
                                    <span
                                        class="theme-preview-chip"
                                        :style="{ background: resolvedActive.colors.accent, color: resolvedActive.colors.surface }"
                                    >Send</span>
                                    <span
                                        class="theme-preview-chip-outline"
                                        :style="{ borderColor: resolvedActive.colors.success, color: resolvedActive.colors.success }"
                                    >Approved</span>
                                    <span
                                        class="theme-preview-chip-outline"
                                        :style="{ borderColor: resolvedActive.colors.warning, color: resolvedActive.colors.warning }"
                                    >Needs review</span>
                                    <span
                                        class="theme-preview-chip-outline"
                                        :style="{ borderColor: resolvedActive.colors.danger, color: resolvedActive.colors.danger }"
                                    >Reject</span>
                                </div>
                            </div>
                        </v-card>
                    </v-col>
                </v-row>

                <v-card variant="flat" color="surface" class="pa-4">
                    <div class="text-subtitle-1 mb-2">Import / export</div>
                    <div class="d-flex flex-wrap align-center" style="gap:12px">
                        <v-btn prepend-icon="mdi-download-outline" variant="tonal" @click="exportCurrent">Export current theme</v-btn>
                        <v-file-input
                            v-model="importFile"
                            label="Import theme (.json)"
                            accept=".json"
                            density="compact"
                            variant="outlined"
                            hide-details
                            prepend-icon="mdi-file-upload-outline"
                            style="max-width:320px"
                            @update:model-value="onImportFile"
                        ></v-file-input>
                    </div>
                    <v-alert v-if="importError" type="error" variant="tonal" density="compact" class="mt-3">
                        {{ importError }}
                    </v-alert>
                </v-card>
            </v-col>
        </v-row>
    </div>
</template>

<script>
import { v4 as uuidv4 } from 'uuid';
import ConfirmActionInline from './ConfirmActionInline.vue';
import { isHex, normalizeHex } from '@/theme/colorMath.js';
import { PALETTE_KEYS } from '@/theme/palette.js';
import { CORE_ROLES } from '@/theme/roles.js';
import { BUILTIN_PRESETS, getPreset, DEFAULT_PRESET_ID } from '@/theme/presets.js';
import { resolveTheme, themeFromConfig } from '@/theme/engine.js';
import { exportTheme, parseThemeFile } from '@/theme/themeFile.js';

function defaultThemeSettings() {
    return { active: DEFAULT_PRESET_ID, custom: [] };
}

export default {
    name: 'AppConfigAppearanceTheme',
    components: {
        ConfirmActionInline,
    },
    props: {
        immutableConfig: Object,
        sceneActive: Boolean,
    },
    emits: ['changed'],
    data() {
        return {
            selectedPaletteKey: 'orange',
            hexDraft: '',
            renamingId: null,
            renameDraft: '',
            importFile: null,
            importError: null,
            isHydrating: false,
            paletteKeys: PALETTE_KEYS,
            coreRoles: CORE_ROLES,
            mainPresets: BUILTIN_PRESETS.filter((p) => p.group === 'main'),
            visionPresets: BUILTIN_PRESETS.filter((p) => p.group === 'vision'),
        };
    },
    computed: {
        // The live `appearance.theme` subtree of the config this page edits
        // in place (see Task 3's watcher / the parent's `onAppearanceChanged`
        // — this page carries no internal copy of its own, unlike
        // AppConfigAppearanceScene/Assets).
        themeSettings() {
            return this.immutableConfig?.appearance?.theme || null;
        },
        activeId() {
            return this.themeSettings?.active;
        },
        customThemes() {
            return this.themeSettings?.custom || [];
        },
        activeCustomTheme() {
            const settings = this.themeSettings;
            if (!settings) return null;
            return (settings.custom || []).find((c) => c.id === settings.active) || null;
        },
        isCustomActive() {
            return !!this.activeCustomTheme;
        },
        resolvedActive() {
            return themeFromConfig(this.themeSettings || defaultThemeSettings());
        },
        usedByLabel() {
            const matches = CORE_ROLES.filter(
                (role) => this.resolvedActive.roleRefs[role.id] === this.selectedPaletteKey
            ).map((role) => role.label);
            return matches.length ? matches.join(', ') : 'surfaces and text';
        },
        // Light/dark for Vuetify (its own opacities and variables) and
        // CodeMirror. Only a theme of your own can change it; the setter
        // edits the live config, so the preview follows at once.
        darkValue: {
            get() {
                return !!this.resolvedActive.dark;
            },
            set(value) {
                if (!this.isCustomActive) return;
                this.activeCustomTheme.dark = !!value;
            },
        },
        colorPickerValue: {
            get() {
                return this.resolvedActive.palette[this.selectedPaletteKey];
            },
            set(value) {
                this.onColorPicked(value);
            },
        },
    },
    watch: {
        immutableConfig: {
            handler(newVal) {
                // Suppress 'changed' emits while the parent swaps the whole
                // config object (initial load, discard, reload) — see
                // AppConfigAppearanceScene.vue's identical pattern.
                this.isHydrating = true;
                if (newVal && newVal.appearance && !newVal.appearance.theme) {
                    newVal.appearance.theme = defaultThemeSettings();
                }
                this.syncHexDraft();
                this.$nextTick(() => {
                    this.isHydrating = false;
                });
            },
            immediate: true,
        },
        themeSettings: {
            handler(newVal, oldVal) {
                if (oldVal !== undefined && !this.isHydrating) {
                    this.$emit('changed');
                }
            },
            deep: true,
        },
        selectedPaletteKey() {
            this.syncHexDraft();
        },
        activeId() {
            this.syncHexDraft();
        },
    },
    methods: {
        syncHexDraft() {
            const hex = this.resolvedActive?.palette?.[this.selectedPaletteKey];
            this.hexDraft = hex || '';
        },
        // Four representative swatches for a preset-list entry (bg, orange,
        // yellow, blue) — `theme` is either a BUILTIN_PRESETS entry (has
        // `.group`) or a custom theme entry (resolved against its base).
        swatchesFor(theme) {
            let palette;
            if (theme.group) {
                palette = theme.palette;
            } else {
                const base = getPreset(theme.base) || getPreset(DEFAULT_PRESET_ID);
                palette = resolveTheme(base, { palette: theme.palette || {}, roles: {} }).palette;
            }
            return [palette.bg, palette.orange, palette.yellow, palette.blue];
        },
        swatchButtonStyle(key) {
            const isSelected = this.selectedPaletteKey === key;
            const ringColor = isSelected ? this.resolvedActive.colors.accent : this.resolvedActive.colors.border;
            return {
                background: this.resolvedActive.palette[key],
                border: `2px solid ${ringColor}`,
            };
        },
        selectActive(id) {
            if (!this.themeSettings) return;
            this.themeSettings.active = id;
        },
        duplicateCurrent() {
            if (!this.themeSettings) return;
            const resolved = this.resolvedActive;
            const base = this.isCustomActive ? this.activeCustomTheme.base : this.activeId;
            const newTheme = {
                id: 'custom-' + uuidv4(),
                name: `${resolved.name} copy`,
                base,
                dark: resolved.dark,
                palette: { ...resolved.palette },
                roles: {},
            };
            if (!this.themeSettings.custom) {
                this.themeSettings.custom = [];
            }
            this.themeSettings.custom.push(newTheme);
            this.themeSettings.active = newTheme.id;
        },
        startRename(theme) {
            this.renamingId = theme.id;
            this.renameDraft = theme.name;
        },
        commitRename(theme) {
            if (this.renamingId !== theme.id) return;
            const trimmed = (this.renameDraft || '').trim();
            if (trimmed) {
                theme.name = trimmed;
            }
            this.renamingId = null;
        },
        cancelRename() {
            this.renamingId = null;
        },
        deleteTheme(theme) {
            const settings = this.themeSettings;
            if (!settings) return;
            const idx = (settings.custom || []).findIndex((c) => c.id === theme.id);
            if (idx === -1) return;
            const wasActive = settings.active === theme.id;
            settings.custom.splice(idx, 1);
            if (wasActive) {
                settings.active = theme.base;
            }
        },
        roleValue(roleId) {
            return this.resolvedActive.roleRefs[roleId];
        },
        setRole(roleId, value) {
            if (!this.isCustomActive) return;
            this.activeCustomTheme.roles[roleId] = value;
        },
        onHexInput(value) {
            this.hexDraft = value;
            if (!this.isCustomActive) return;
            const normalized = normalizeHex(value);
            if (normalized && isHex(normalized)) {
                this.activeCustomTheme.palette[this.selectedPaletteKey] = normalized;
            }
        },
        onColorPicked(value) {
            if (!this.isCustomActive) return;
            const normalized = normalizeHex(value);
            if (normalized && isHex(normalized)) {
                this.activeCustomTheme.palette[this.selectedPaletteKey] = normalized;
                this.hexDraft = normalized;
            }
        },
        exportSubject() {
            if (this.isCustomActive) {
                return this.activeCustomTheme;
            }
            const preset = getPreset(this.activeId) || getPreset(DEFAULT_PRESET_ID);
            return {
                id: preset.id,
                name: preset.name,
                base: preset.id,
                dark: preset.dark,
                palette: preset.palette,
                roles: preset.roles || {},
            };
        },
        exportCurrent() {
            const subject = this.exportSubject();
            const data = exportTheme(subject);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${subject.name}.fantasymate-theme.json`;
            a.click();
            URL.revokeObjectURL(url);
        },
        onImportFile(value) {
            const file = Array.isArray(value) ? value[0] : value;
            this.importError = null;
            if (!file) return;
            const reader = new FileReader();
            reader.onload = () => {
                const parsed = parseThemeFile(reader.result);
                if (!parsed.ok) {
                    this.importError = parsed.error;
                    this.importFile = null;
                    return;
                }
                const settings = this.themeSettings;
                if (!settings) return;
                if (!settings.custom) settings.custom = [];
                let name = parsed.theme.name;
                const existingNames = new Set(settings.custom.map((c) => c.name));
                if (existingNames.has(name)) {
                    let n = 2;
                    while (existingNames.has(`${name} (${n})`)) {
                        n += 1;
                    }
                    name = `${name} (${n})`;
                }
                settings.custom.push({
                    id: 'custom-' + uuidv4(),
                    name,
                    base: parsed.theme.base,
                    dark: parsed.theme.dark,
                    palette: parsed.theme.palette,
                    roles: parsed.theme.roles,
                });
                this.importFile = null;
            };
            reader.onerror = () => {
                this.importError = 'Could not read the file.';
                this.importFile = null;
            };
            reader.readAsText(file);
        },
    },
};
</script>

<style scoped>
.theme-swatch-chip {
    display: inline-block;
    width: 8px;
    height: 18px;
    border-radius: 2px;
}

.theme-swatch {
    width: 44px;
    height: 44px;
    border-radius: 6px;
    cursor: pointer;
    padding: 0;
}

.role-swatch {
    display: inline-block;
    width: 16px;
    height: 16px;
    border-radius: 4px;
    flex-shrink: 0;
}

.theme-preview-tab {
    padding: 10px 10px;
    font-size: 13px;
}

.theme-preview-badge {
    font-size: 11px;
    font-weight: 600;
    border-radius: 999px;
    padding: 1px 6px;
    margin-left: 4px;
}

.theme-preview-chip {
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 600;
    font-size: 13px;
}

.theme-preview-chip-outline {
    border: 1px solid;
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
}
</style>
