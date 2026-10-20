// The fantasymate world screens' state (Worlds home, World tab, thing
// pages, create box), kept in step with the backend's `worlds` websocket
// router (src/talemate/server/worlds.py).
//
// Actions send `{type: 'worlds', action, ...}` through the function given
// to `connect`. Replies come back as `{type: 'worlds', action, data}`;
// TalemateApp registers `handleMessage` as one websocket message handler,
// and it fills the state. Errors arrive as `operation_done` with
// `error.message` (and as `preview_failed`/`prose_failed`).
//
// The backend holds one open world per connection and closes it when the
// connection goes, so a disconnect forgets the open world. Opening another
// world cancels a running preview without any reply, so opening (or
// creating) a world clears the preview and every spinner itself.
//
// No `@/` imports: the node checks (checks/worlds.check.mjs) load this file.

import { defineStore } from 'pinia';

import { LISTED_KINDS } from '../components/worlds/worldKinds.js';

const ROUTER = 'worlds';

// replies to these clear their own spinner (`pending[action]`)
const EDIT_ACTIONS = ['add_fact', 'correct_fact', 'end_fact', 'remove_fact', 'set_field'];

function emptyThings() {
    return Object.fromEntries(LISTED_KINDS.map((kind) => [kind, []]));
}

function worldState() {
    // everything that belongs to the open world
    return {
        things: emptyThings(),
        // the thing page: which thing, its payload, and the date it's viewed as of
        selectedThingId: null,
        thing: null,
        thingAt: null,
        scenes: [],
        // the create box: the request being previewed, and its reply
        previewRequest: null,
        previewPending: false,
        preview: null,
        previewError: null,
        // the id of the thing whose prose is being regenerated
        proseRegenerating: null,
        pending: {},
    };
}

// the function actions send with; set by `connect`
let send = null;

export const useWorldsStore = defineStore('worlds', {
    state: () => ({
        connected: false,
        worlds: [],
        currentWorld: null,
        error: null,
        ...worldState(),
    }),

    getters: {
        calendar: (state) => state.currentWorld?.calendar || null,
    },

    actions: {
        // --- the connection -----------------------------------------------

        connect(sendFn) {
            send = sendFn;
            this.connected = true;
            this.listWorlds();
        },

        disconnected() {
            this.connected = false;
            this.currentWorld = null;
            Object.assign(this, worldState());
        },

        request(action, data = {}) {
            if (!send) {
                return;
            }
            send({ type: ROUTER, action, ...data });
        },

        clearError() {
            this.error = null;
        },

        // --- worlds -------------------------------------------------------

        listWorlds() {
            this.request('list_worlds');
        },

        createWorld(name, presentYear) {
            this.resetWorld();
            this.pending = { create_world: true };
            this.request('create_world', { name, present_year: presentYear });
        },

        openWorld(path) {
            this.resetWorld();
            this.pending = { open_world: true };
            this.request('open_world', { path });
        },

        // a world switch cancels the backend's preview without a reply, so
        // nothing of the old world may wait for one
        resetWorld() {
            Object.assign(this, worldState());
        },

        listScenes() {
            this.request('list_scenes');
        },

        // --- things -------------------------------------------------------

        listThings(kind) {
            this.request('list_things', { kind });
        },

        openThing(id, at = null) {
            this.selectedThingId = id;
            this.thingAt = at;
            if (this.thing?.id !== id) {
                this.thing = null;
            }
            this.request('get_thing', { id, at });
        },

        closeThing() {
            this.selectedThingId = null;
            this.thing = null;
            this.thingAt = null;
        },

        viewThingAt(at) {
            if (this.selectedThingId) {
                this.openThing(this.selectedThingId, at);
            }
        },

        // --- create -------------------------------------------------------

        previewThing(kind, prompt, fields = {}) {
            this.previewRequest = { kind, prompt, fields };
            this.preview = null;
            this.previewError = null;
            this.previewPending = true;
            this.request('preview_thing', { kind, prompt, fields });
        },

        regeneratePreview() {
            const req = this.previewRequest;
            if (req) {
                this.previewThing(req.kind, req.prompt, req.fields);
            }
        },

        // drop the preview, keeping the request so the prompt can be edited
        discardPreview() {
            this.preview = null;
            this.previewError = null;
            this.previewPending = false;
        },

        acceptPreview(changes = {}) {
            if (!this.preview) {
                return;
            }
            this.pending = { ...this.pending, accept_preview: true };
            this.request('accept_preview', { preview: { ...this.preview, ...changes } });
        },

        // --- edits (each answers with the thing as of `thingAt`) -----------

        edit(action, data) {
            this.pending = { ...this.pending, [action]: true };
            this.request(action, { thing_id: this.selectedThingId, at: this.thingAt, ...data });
        },

        addFact(category, text, validFrom = null, validUntil = null) {
            this.edit('add_fact', { category, text, valid_from: validFrom, valid_until: validUntil });
        },

        // `changes` holds only what changes: text, category, valid_from,
        // valid_until (a null date makes that end open)
        correctFact(factId, changes) {
            this.edit('correct_fact', { fact_id: factId, ...changes });
        },

        endFact(factId, until) {
            this.edit('end_fact', { fact_id: factId, until });
        },

        removeFact(factId) {
            this.edit('remove_fact', { fact_id: factId });
        },

        regenerateProse() {
            if (!this.selectedThingId) {
                return;
            }
            this.proseRegenerating = this.selectedThingId;
            this.request('regenerate_prose', { id: this.selectedThingId, at: this.thingAt });
        },

        // --- replies ------------------------------------------------------

        worldOpened(info) {
            this.resetWorld();
            this.currentWorld = info;
            for (const kind of LISTED_KINDS) {
                this.listThings(kind);
            }
            this.listScenes();
        },

        clearPending(action) {
            if (this.pending[action]) {
                const { [action]: _done, ...rest } = this.pending;
                this.pending = rest;
            }
        },

        handleMessage(message) {
            if (message?.type !== ROUTER) {
                return;
            }
            const data = message.data;
            const action = message.action;

            switch (action) {
                case 'list_worlds':
                    this.worlds = data.worlds;
                    break;
                case 'create_world':
                    this.worldOpened(data);
                    this.listWorlds();
                    break;
                case 'open_world':
                    this.worldOpened(data);
                    break;
                case 'get_present':
                case 'set_present':
                    if (this.currentWorld) {
                        this.currentWorld = { ...this.currentWorld, ...data };
                    }
                    break;
                case 'list_things':
                    this.things = { ...this.things, [data.kind]: data.things };
                    break;
                case 'get_thing':
                    if (data.id === this.selectedThingId) {
                        this.thing = data;
                    }
                    break;
                case 'list_scenes':
                    this.scenes = data.scenes;
                    break;
                case 'preview_thing':
                    if (this.previewPending) {
                        this.preview = data;
                        this.previewPending = false;
                    }
                    break;
                case 'preview_failed':
                    if (this.previewPending) {
                        this.previewError = message.message;
                        this.previewPending = false;
                    }
                    break;
                case 'accept_preview':
                    this.preview = null;
                    this.previewRequest = null;
                    this.selectedThingId = data.id;
                    this.thingAt = null;
                    this.thing = data;
                    this.listThings(data.kind);
                    break;
                case 'prose_updated':
                    if (this.proseRegenerating === data.id) {
                        this.proseRegenerating = null;
                    }
                    if (data.id === this.selectedThingId) {
                        this.request('get_thing', { id: data.id, at: this.thingAt });
                    }
                    break;
                case 'prose_failed':
                    if (this.proseRegenerating === data?.id) {
                        this.proseRegenerating = null;
                    }
                    this.error = message.message;
                    break;
                case 'operation_done':
                    if (message.error) {
                        // the failed request can't be told apart, so every
                        // spinner stops
                        this.error = message.error.message;
                        this.pending = {};
                        this.previewPending = false;
                        this.proseRegenerating = null;
                    }
                    break;
                default:
                    if (EDIT_ACTIONS.includes(action) && data.id === this.selectedThingId) {
                        this.thing = data;
                        if (action === 'set_field') {
                            this.listThings(data.kind);
                        }
                    }
            }
            this.clearPending(action);
        },
    },
});
