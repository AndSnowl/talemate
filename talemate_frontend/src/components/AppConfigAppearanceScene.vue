<template>
    <div class="ma-3">
        <v-table density="compact">
            <thead>
                <tr>
                    <th class="text-left" style="padding: 8px 12px;">Style</th>
                    <th class="text-left" style="padding: 8px 12px;">Italic</th>
                    <th class="text-left" style="padding: 8px 12px;">Bold</th>
                    <th class="text-left" style="padding: 8px 12px;">Show</th>
                    <th class="text-left" style="padding: 8px 12px;">Color</th>
                    <th class="text-right" style="padding: 8px 12px;">Actions</th>
                </tr>
            </thead>
            <tbody>
                <template v-for="(styleConfig, typ) in config" :key="typ">
                    <tr v-if="typ.endsWith('_messages') || ['quotes', 'parentheses', 'brackets', 'emphasis', 'entities'].includes(typ)" :style="colorPickerTarget === typ ? 'background-color: rgba(128, 128, 128, 0.1);' : ''">
                        <td style="padding: 4px 12px;">
                            <div class="d-flex align-center">
                                <div class="text-caption font-weight-medium">{{ typLabelMap[typ] || typ }}</div>
                                <v-chip v-if="typ === 'quotes'" size="x-small" variant="text" class="ml-1">" "</v-chip>
                                <v-chip v-if="typ === 'parentheses'" size="x-small" variant="text" class="ml-1">( )</v-chip>
                                <v-chip v-if="typ === 'brackets'" size="x-small" variant="text" class="ml-1">[ ]</v-chip>
                                <v-chip v-if="typ === 'emphasis'" size="x-small" variant="text" class="ml-1">* *</v-chip>
                                <v-chip v-if="typ === 'entities'" size="x-small" variant="text" class="ml-1">entity</v-chip>
                            </div>
                        </td>
                        <td style="padding: 4px 12px;">
                            <v-checkbox color="primary" :disabled="!canSetStyleOn[typ]" density="compact" hide-details v-model="styleConfig.italic" class="ma-0"></v-checkbox>
                        </td>
                        <td style="padding: 4px 12px;">
                            <v-checkbox color="primary" :disabled="!canSetStyleOn[typ]" density="compact" hide-details v-model="styleConfig.bold" class="ma-0"></v-checkbox>
                        </td>
                        <td style="padding: 4px 12px;">
                            <v-checkbox color="primary" v-if="canSetShowOn[typ]" density="compact" hide-details v-model="styleConfig.show" class="ma-0"></v-checkbox>
                        </td>
                        <td style="padding: 4px 12px;">
                            <v-checkbox color="primary" v-if="['quotes', 'parentheses', 'brackets', 'emphasis', 'entities'].includes(typ)" density="compact" hide-details v-model="styleConfig.override_color" class="ma-0"></v-checkbox>
                        </td>
                        <td class="text-right" style="padding: 4px 12px;" v-if="canSetColorOn[typ]">
                            <div class="d-flex align-center justify-end">
                                <v-menu>
                                    <template v-slot:activator="{ props }">
                                        <v-btn
                                            v-bind="props"
                                            size="x-small"
                                            variant="outlined"
                                            :color="getColor(typ, styleConfig.color)"
                                            class="mr-1"
                                        >
                                            <v-icon start size="small">mdi-palette</v-icon>
                                            Color
                                        </v-btn>
                                    </template>
                                    <v-list density="compact">
                                        <v-list-item
                                            v-for="key in paletteKeys"
                                            :key="key"
                                            @click="selectPaletteColor(typ, key)"
                                        >
                                            <template v-slot:prepend>
                                                <v-avatar size="16" :color="paletteSwatch(key)" class="mr-2"></v-avatar>
                                            </template>
                                            <v-list-item-title>{{ key }}</v-list-item-title>
                                        </v-list-item>
                                        <v-divider></v-divider>
                                        <v-list-item @click="openColorPicker(typ, getColor(typ, styleConfig.color))">
                                            <v-list-item-title>Custom…</v-list-item-title>
                                        </v-list-item>
                                    </v-list>
                                </v-menu>
                                <v-btn size="x-small" color="secondary" variant="text" prepend-icon="mdi-refresh" @click="reset(typ, styleConfig)">Reset</v-btn>
                            </div>
                        </td>
                        <td v-else style="padding: 4px 12px;"></td>
                    </tr>
                </template>
            </tbody>
        </v-table>
    </div>
    <v-row class="ma-5" no-gutters>
        <v-col cols="8" class="pr-3">
            <v-card color="surface">
                <v-card-text>
                    <div>
                        <div class="mb-2 d-flex align-center">
                            <v-icon class="mr-2" :color="getColor('narrator_messages', config.narrator_messages?.color)">mdi-script-text-outline</v-icon>
                            <span :style="buildCssStyles('narrator_messages', config.narrator_messages)" v-html="renderedNarratorMessagePreview">
                            </span>
                        </div>
                        <div class="mb-2 d-flex align-center">
                            <v-icon class="mr-2" :color="getColor('actor_messages', config.actor_messages?.color)">mdi-chat-outline</v-icon>
                            <span :style="buildCssStyles('actor_messages', config.actor_messages)" v-html="renderedActorMessagePreview">
                            </span>
                        </div>
                        <div class="mt-3">
                            <v-chip :color="getColor('director_messages', config.director_messages.color)">
                                <v-icon class="mr-2">mdi-bullhorn-outline</v-icon>
                                <span @click="toggle()">Guy looking at fox</span>
                            </v-chip>
                        </div>
                        <div class="mt-3 d-flex align-center" :style="buildCssStyles('director_messages', config.director_messages)">
                            <v-icon class="mr-2" :color="getColor('director_messages', config.director_messages?.color)">mdi-bullhorn-outline</v-icon>
                            <span>Director instructs</span>
                            <span class="ml-1 text-decoration-underline">Guy looking at fox</span>
                            <span class="ml-1">Stop looking at the fox.</span>
                        </div>
                        <div class="mt-3 d-flex align-center">
                            <v-icon class="mr-2" :color="getColor('time_messages', config.time_messages?.color)">mdi-clock-outline</v-icon>
                            <span :style="buildCssStyles('time_messages', config.time_messages)">
                                3 days layer
                            </span>
                        </div>
                        <div class="mt-3 d-flex align-center" :style="buildCssStyles('context_investigation_messages', config.context_investigation_messages)">
                            <v-icon class="mr-2" :color="getColor('context_investigation_messages', config.context_investigation_messages?.color)">mdi-text-search</v-icon>
                            <span v-html="renderedContextInvestigationPreview">
                            </span>
                        </div>
                        <div class="mt-3 d-flex align-center" :style="buildCssStyles('information_messages', config.information_messages)">
                            <v-icon class="mr-2" :color="getColor('information_messages', config.information_messages?.color)">mdi-information-outline</v-icon>
                            <span>
                                A heads-up or system notice for the player.
                            </span>
                        </div>
                        <div class="mt-3 d-flex align-center">
                            <v-icon class="mr-2" :color="getColor('entities', config.entities?.color)">mdi-cursor-default-click-outline</v-icon>
                            <span :style="buildCssStyles('narrator_messages', config.narrator_messages)" v-html="renderedEntityHighlightsPreview">
                            </span>
                        </div>
                    </div>
                </v-card-text>
            </v-card>
        </v-col>
        <v-col cols="4">
            <div :style="'opacity: '+(colorPickerTarget ? 1 : 0)">
                <v-color-picker mode="hex" :disabled="colorPickerTarget === null" v-model="color" @update:model-value="onColorChange"></v-color-picker>
            </div>
        </v-col>
    </v-row>
</template>

<script>
import { SceneTextParser } from '@/utils/sceneMessageRenderer';
import { getMessageColor } from '@/utils/messageColors.js';
import { PALETTE_KEYS } from '@/theme/palette.js';
import { currentTheme } from '@/theme/store.js';

export default {
    name: 'AppConfigAppearanceScene',
    components: {
    },
    props: {
        immutableConfig: Object,
        sceneActive: Boolean,
    },
    emits: [
        'changed',
    ],
    watch: {
        immutableConfig: {
            handler: function(newVal) {
                // Suppress changed events during hydration
                this.isHydrating = true;
                
                if(!newVal) {
                    this.config = {};
                    this.isHydrating = false;
                    return;
                }

                const sceneConfig = {...newVal.appearance.scene};
                // Handle migration from character_messages to actor_messages
                if (sceneConfig.character_messages && !sceneConfig.actor_messages) {
                    sceneConfig.actor_messages = sceneConfig.character_messages;
                    delete sceneConfig.character_messages;
                }
                // Ensure new styling fields exist with defaults if missing
                this.hydrateMarkupStyle(sceneConfig, 'quotes');
                this.hydrateMarkupStyle(sceneConfig, 'parentheses', { italic: true, withShow: true });
                this.hydrateMarkupStyle(sceneConfig, 'brackets', { italic: true, withShow: true });
                this.hydrateMarkupStyle(sceneConfig, 'emphasis', { italic: true });
                this.hydrateMarkupStyle(sceneConfig, 'entities', { withShow: true });
                this.config = sceneConfig;
                
                // Re-enable changed events after hydration completes
                this.$nextTick(() => {
                    this.isHydrating = false;
                });
            },
            immediate: true,
            deep: true,
        },
        config: {
            handler: function(newVal, oldVal) {
                // Emit changed event when config changes (for live preview)
                // Skip initial emit (when oldVal is undefined) and during hydration
                if (oldVal !== undefined && !this.isHydrating) {
                    this.$emit('changed');
                }
            },
            deep: true,
        },
    },
    computed: {
        renderedNarratorMessagePreview() {
            const sceneConfig = this.config || {};
            const narratorStyles = sceneConfig.narrator_messages || {};
            
            const parser = new SceneTextParser({
                quotes: sceneConfig.quotes,
                emphasis: sceneConfig.emphasis || narratorStyles,
                parentheses: sceneConfig.parentheses || narratorStyles,
                brackets: sceneConfig.brackets || narratorStyles,
                default: narratorStyles,
                messageType: 'narrator',
            });

            return parser.parse('The quick brown fox jumps over the lazy dog. "Did you see that?" he wondered (with some surprise). The moment felt [significant] and *unforgettable*.');
        },
        renderedActorMessagePreview() {
            const sceneConfig = this.config || {};
            const actorStyles = sceneConfig.actor_messages || sceneConfig.character_messages || {};
            const narratorStyles = sceneConfig.narrator_messages || {};
            
            // Merge actor styles with narrator styles as fallback for defaults
            const defaultStyles = {
                color: actorStyles.color != null ? actorStyles.color : undefined,
                italic: actorStyles.italic ?? narratorStyles.italic,
                bold: actorStyles.bold ?? narratorStyles.bold,
            };
            
            const parser = new SceneTextParser({
                quotes: sceneConfig.quotes,
                emphasis: sceneConfig.emphasis || narratorStyles,
                parentheses: sceneConfig.parentheses || narratorStyles,
                brackets: sceneConfig.brackets || narratorStyles,
                default: defaultStyles,
                messageType: 'actor',
            });

            return parser.parse('John walked into the room. "Wow, that was a quick brown fox - did you see it?" he exclaimed (still catching his breath). The scene was [dramatic] and *intense*.');
        },
        renderedContextInvestigationPreview() {
            const sceneConfig = this.config || {};
            const actorStyles = sceneConfig.actor_messages || sceneConfig.character_messages || {};
            const contextStyles = sceneConfig.context_investigation_messages || {};
            
            const parser = new SceneTextParser({
                quotes: sceneConfig.quotes,
                emphasis: sceneConfig.emphasis || contextStyles,
                parentheses: sceneConfig.parentheses || contextStyles,
                brackets: sceneConfig.brackets || contextStyles,
                default: contextStyles,
                messageType: 'context_investigation',
            });
            
            return parser.parse('The fox has reddish-brown fur with white underbelly. According to the field guide, "foxes typically weigh between 6-15 pounds".');
        },
        renderedEntityHighlightsPreview() {
            const sceneConfig = this.config || {};
            const narratorStyles = sceneConfig.narrator_messages || {};

            const parser = new SceneTextParser({
                quotes: sceneConfig.quotes,
                emphasis: sceneConfig.emphasis || narratorStyles,
                parentheses: sceneConfig.parentheses || narratorStyles,
                brackets: sceneConfig.brackets || narratorStyles,
                entities: sceneConfig.entities,
                default: narratorStyles,
                messageType: 'narrator',
            });

            return parser.parse(
                'Elmer approaches the blast door, eyes scanning toward the conduit chamber beyond.',
                {
                    mentions: [
                        { name: 'Elmer', kind: 'character', phrases: ['Elmer'] },
                        { name: 'Blast door', kind: 'item', phrases: ['the blast door'] },
                        { name: 'Conduit chamber', kind: 'place', phrases: ['the conduit chamber'] },
                    ],
                },
            );
        },
    },
    data() {
        return {
            colorPicker: null,
            color: "#000000",
            colorPickerTarget: null,
            paletteKeys: PALETTE_KEYS,
            typLabelMap: {
                "narrator_messages": "Narrator Messages",
                "actor_messages": "Actor Messages",
                "director_messages": "Director Messages",
                "time_messages": "Time Messages",
                "context_investigation_messages": "Context Investigations",
                "information_messages": "Information Messages",
                "quotes": "Quotes",
                "parentheses": "Parentheses",
                "brackets": "Brackets",
                "emphasis": "Emphasis",
                "entities": "Entity Highlights",
            },
            config: {
                scene: {}
            },
            isHydrating: false, // Flag to suppress changed events during initialization
            canSetStyleOn: {
                "narrator_messages": true,
                "actor_messages": true,
                "director_messages": true,
                "context_investigation_messages": true,
                "information_messages": true,
                "quotes": true,
                "parentheses": true,
                "brackets": true,
                "emphasis": true,
                "entities": true,
                //"time_messages": true,
            },
            canSetColorOn: {
                "narrator_messages": true,
                "actor_messages": true,
                "director_messages": true,
                "time_messages": true,
                "context_investigation_messages": true,
                "information_messages": true,
                "quotes": true,
                "parentheses": true,
                "brackets": true,
                "emphasis": true,
                "entities": true,
            },
            canSetShowOn: {
                "director_messages": true,
                "context_investigation_messages": true,
                "parentheses": true,
                "brackets": true,
                "entities": true,
            },
        }
    },
    methods: {
        // Backfill defaults for a markup-style entry on the scene appearance
        // config. Used by the immutableConfig watcher to migrate older configs
        // that pre-date newer fields (override_color, show) and to seed a
        // fresh entry when the markup type isn't present at all.
        hydrateMarkupStyle(sceneConfig, key, { italic = false, bold = false, withShow = false } = {}) {
            if (!sceneConfig[key]) {
                const fresh = {
                    // Unset — resolved to the type's theme role colour by
                    // getMessageColor/getColor below.
                    color: null,
                    italic,
                    bold,
                    override_color: true,
                };
                if (withShow) fresh.show = true;
                sceneConfig[key] = fresh;
                return;
            }
            if (sceneConfig[key].override_color === undefined) {
                sceneConfig[key].override_color = true;
            }
            if (withShow && sceneConfig[key].show === undefined) {
                sceneConfig[key].show = true;
            }
        },
        reset(typ, config) {
            config.color = null;
            this.color = this.getColor(typ, config.color);
        },
        onColorChange() {
            if (this.colorPickerTarget && this.config[this.colorPickerTarget]) {
                this.config[this.colorPickerTarget].color = this.color;
            }
        },
        // A palette swatch picked from the "Color" menu stores the key
        // string (e.g. "teal") as the colour, rather than a hex value.
        selectPaletteColor(typ, key) {
            if (this.config[typ]) {
                this.config[typ].color = key;
            }
        },
        // The hex a palette key currently resolves to, for swatch previews.
        paletteSwatch(key) {
            return currentTheme.value.palette[key];
        },
        buildCssStyles(typ, config) {
            if (!config) {
                config = {};
            }
            let styles = "";
            if (config.italic) {
                styles += "font-style: italic;";
            }
            if (config.bold) {
                styles += "font-weight: bold;";
            }
            styles += "color: " + this.getColor(typ, config.color) + ";";
            return styles;
        },
        openColorPicker(target, targetColor) {
            this.color = targetColor;
            this.colorPicker = true;
            this.colorPickerTarget = target;
        },

        // Resolve `typ`'s effective colour through the theme — a palette
        // key resolves to that palette hex, an unset/legacy-default colour
        // falls back to the type's theme role colour, and any other hex is
        // kept as-is. See utils/messageColors.js's getMessageColor.
        //
        // `color` itself isn't used (this.config already holds the same
        // value `styleConfig.color`/`config.color` reads at the call
        // sites) — the parameter stays so every existing call site keeps
        // its current shape.
        getColor(typ, _color) {
            // Message-type keys use the `_messages` suffix in the config UI
            // (e.g. "narrator_messages") but getMessageColor expects the
            // bare type name — strip the suffix on lookup.
            const key = typ.endsWith('_messages') ? typ.slice(0, -'_messages'.length) : typ;
            return getMessageColor({ scene: this.config }, key, currentTheme.value);
        }
    },
}

</script>

<style scoped>
/* Mirror SceneMessages .scene-entity styling — underline tracks inline color via currentColor. */
.v-card-text :deep(.scene-entity) {
    cursor: pointer;
    text-decoration: underline dotted currentColor;
    text-underline-offset: 3px;
    border-radius: 2px;
}
</style>