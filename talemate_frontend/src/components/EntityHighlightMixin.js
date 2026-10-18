import EntityTooltip from './EntityTooltip.vue';
import {
    dispatchExamineEntity,
    dispatchLookAtEntity,
    isKnownSceneCharacter,
} from '@/utils/entityActions';
import { culturesStory } from '@/components/cultures/culturesStory.js';
import {
    foreignMentions,
    buildNameIndex,
    markUnreviewed,
    combineMentions,
    findLexiconEntry,
} from '@/components/cultures/storyLexicon.js';
import '@/components/cultures/story.css';

// Shared empty array for messages with no entity highlights — using the same
// reference avoids invalidating the entityMentions prop on every parent render.
const NO_ENTITY_MENTIONS = Object.freeze([]);

/**
 * Inline entity-highlight + tooltip behaviour for the chat view.
 *
 * Drives the "examine in the latest message" affordance: receives the
 * world_state event payload, exposes a per-message mention list to feed to
 * the SceneTextParser, owns the popover lifecycle for the click-tooltip,
 * and dispatches the examine→context-investigation flow when the user
 * clicks "Examine" on a highlighted entity.
 *
 * Requirements on the host component:
 *  - Template: bind `:entityMentions="getEntityMentionsForMessage(message.id)"`
 *    on every message component that should render highlights, and add
 *    `@click="onMessageContainerClick"` on the message container element.
 *  - Template: mount `<EntityTooltip
 *        :model-value="entityTooltip.open"
 *        :activator="entityTooltip.activator"
 *        :entity="entityTooltip.entity"
 *        @update:model-value="onEntityTooltipUpdate"
 *        @configure-highlights="onConfigureEntityHighlights"
 *        @examine="triggerExamineEntity"
 *        @look-at="triggerLookAtEntity" />`.
 *  - In the host's `handleMessage(data)`, call
 *    `this.rebuildWorldStateEntities(data.data)` when
 *    `data.type === 'world_state' && data.status !== 'requested' && data.data`.
 *  - The host must inject `getWebsocket` — the mixin dispatches the
 *    `world_state_agent.examine_entity` and `narrator.*` actions over the
 *    socket.
 *  - CSS for `.scene-entity` spans lives in the host (scoped + `:deep()`),
 *    since style blocks can't ride along on a mixin.
 */
export default {
    components: { EntityTooltip },

    data() {
        return {
            // World-state entity highlighting state — populated by the
            // 'world_state' websocket event. Highlights are only rendered on
            // messages whose id appears in worldStateAnchorIds (every focus
            // message the agent included in the snapshot pass).
            worldStateAnchorIds: new Set(),
            // Flat list passed to SceneTextParser: [{ name, kind, phrases }]
            worldStateMentions: [],
            // Lookup for tooltip content: { "kind:name": { name, kind, snapshot, emotion } }
            worldStateEntityIndex: {},
            // Entity tooltip popover state
            entityTooltip: {
                open: false,
                activator: null,
                entity: null,
            },
        };
    },

    mounted() {
        document.addEventListener('click', this.onDocumentClickForTooltip);
    },

    beforeUnmount() {
        document.removeEventListener('click', this.onDocumentClickForTooltip);
    },

    computed: {
        // Foreign-word/phrase mentions for the scene's present cultures —
        // rendered on every story message, not just the snapshot's anchors.
        culturesForeignMentions() {
            return foreignMentions(culturesStory.story.lexicon || []);
        },

        // Glossary names, indexed for `markUnreviewed`'s lookup.
        culturesNameIndex() {
            return buildNameIndex(culturesStory.story.names || []);
        },

        // Name mentions (world-state entities, flagged unreviewed where the
        // glossary says so) followed by foreign mentions — names first, so
        // a name wins over a foreign entry with the same text.
        culturesAnchorMentions() {
            return combineMentions(
                markUnreviewed(this.worldStateMentions, this.culturesNameIndex),
                this.culturesForeignMentions,
            );
        },
    },

    methods: {
        // Return the entity-mention list to feed to the SceneTextParser for
        // this message — an anchor message (part of the latest world-state
        // snapshot's focus span) gets names and foreign words; every other
        // message still gets foreign-word highlights. Falls back to the
        // shared empty sentinel so the prop reference stays stable across
        // re-renders when there's nothing to highlight.
        getEntityMentionsForMessage(messageId) {
            if (this.worldStateAnchorIds.has(messageId)) {
                return this.culturesAnchorMentions.length
                    ? this.culturesAnchorMentions
                    : NO_ENTITY_MENTIONS;
            }
            return this.culturesForeignMentions.length
                ? this.culturesForeignMentions
                : NO_ENTITY_MENTIONS;
        },

        // Rebuild the parser-facing mentions list and the tooltip lookup
        // from a fresh world_state event payload.
        rebuildWorldStateEntities(payload) {
            const mentions = [];
            const index = {};
            const ingest = (kind, dict) => {
                if (!dict) return;
                for (const name in dict) {
                    const entry = dict[name] || {};
                    const phrases = Array.isArray(entry.mentions) ? entry.mentions : [];
                    if (phrases.length > 0) {
                        mentions.push({ name, kind, phrases });
                    }
                    index[`${kind}:${name}`] = {
                        name,
                        kind,
                        snapshot: entry.snapshot || null,
                        emotion: entry.emotion || null,
                    };
                }
            };
            ingest('character', payload.characters);
            ingest('item', payload.items);
            ingest('place', payload.places);

            this.worldStateMentions = mentions;
            this.worldStateEntityIndex = index;
            this.worldStateAnchorIds = new Set(payload.anchor_message_ids || []);
        },

        // Delegated click handler on the message container. When the click
        // lands on a `.scene-entity` span emitted by the SceneTextParser,
        // look up the entity and open the tooltip menu anchored to the span.
        onMessageContainerClick(event) {
            const foreignSpan = event.target.closest?.('.scene-foreign');
            if (foreignSpan) {
                const entry = findLexiconEntry(culturesStory.story, foreignSpan.dataset.foreignId);
                if (!entry) return;
                event.stopPropagation();
                this.openEntityTooltip(foreignSpan, { kind: 'foreign', name: entry.text, foreign: entry });
                return;
            }
            const span = event.target.closest?.('.scene-entity');
            if (!span) return;
            const name = span.getAttribute('data-entity-name');
            const kind = span.getAttribute('data-entity-kind');
            if (!name || !kind) return;
            const entity = this.worldStateEntityIndex[`${kind}:${name}`];
            if (!entity) return;
            event.stopPropagation();
            this.openEntityTooltip(span, entity);
        },

        // True when `name` is a live Scene actor (active or inactive roster).
        characterIsKnown(name) {
            return isKnownSceneCharacter(this.scene?.data, name);
        },

        openEntityTooltip(activator, entity) {
            // Stamp whether a character entity is a live Scene actor. Existing
            // characters have their own detail surfaces (sheet, attributes,
            // progression), so Add Detail is hidden for them — but background
            // characters (named in narrative, not actors) have no other
            // fleshing-out path, so they keep it like items and places do.
            const enriched =
                entity?.kind === 'character'
                    ? { ...entity, isKnownCharacter: this.characterIsKnown(entity.name) }
                    : entity;
            this.entityTooltip = { open: true, activator, entity: enriched };
        },

        // Flip the menu closed but keep `activator` and `entity` populated —
        // setting them to null synchronously crashes v-menu's leave
        // transition, which still reads coordinates from the activator while
        // animating out.
        closeEntityTooltip() {
            if (!this.entityTooltip.open) return;
            this.entityTooltip = { ...this.entityTooltip, open: false };
        },

        // We own close behaviour ourselves (the menu is `persistent`).
        // Document-level clicks land here when a click was NOT on an entity
        // span — our delegated handler calls stopPropagation in that case.
        // Clicks inside the menu content are also ignored.
        onDocumentClickForTooltip(event) {
            if (!this.entityTooltip.open) return;
            if (event.target.closest?.('.v-overlay__content')) return;
            if (event.target.closest?.('.scene-entity')) return;
            if (event.target.closest?.('.scene-foreign')) return;
            this.closeEntityTooltip();
        },

        onEntityTooltipUpdate(open) {
            // v-menu emits update:modelValue both for explicit closes and
            // for spurious transitions while the activator changes. We only
            // honour explicit opens — close is owned by closeEntityTooltip.
            if (open && !this.entityTooltip.open) {
                this.entityTooltip = { ...this.entityTooltip, open: true };
            }
        },

        onConfigureEntityHighlights() {
            this.closeEntityTooltip();
            this.$emit('configure-entity-highlights');
        },

        triggerExamineEntity(entity) {
            if (!entity || !entity.snapshot) return;
            this.closeEntityTooltip();
            dispatchExamineEntity(this.getWebsocket(), {
                name: entity.name,
                kind: entity.kind,
                snapshot: entity.snapshot,
            });
        },

        triggerLookAtEntity(entity) {
            if (!entity || !entity.name) return;
            this.closeEntityTooltip();
            dispatchLookAtEntity(this.getWebsocket(), {
                name: entity.name,
                kind: entity.kind,
                isKnownCharacter: this.characterIsKnown(entity.name),
            });
        },
    },
};
