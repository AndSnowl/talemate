// Named UI roles, each pointing at a palette name (see palette.js) — Doom
// Emacs style. A role ref is either a bare palette key string, or
// `{ pal, darken?, lighten?, mix?: { with, t } }` for a derived colour.
//
// Four groups make up the full role set:
//   - CORE_ROLES: the 11 "story" roles (accent, link, scene, ...).
//   - NEUTRAL_ROLES: surfaces and generic text, Material-ish naming.
//   - MESSAGE_ROLES: scene markup/message colours not already covered above.
//   - LEGACY_ROLES: every colour key `plugins/vuetify.js` defines today,
//     minus the ones already named above (muted, narrator, director,
//     context_investigation).
//
// Defaults are picked so the app reads as gruvbox dark under that preset
// (see presets.js).

export const CORE_ROLES = [
    { id: 'accent', label: 'Accent', ref: 'orange' },
    { id: 'link', label: 'Link', ref: 'yellow' },
    { id: 'scene', label: 'Scene', ref: 'teal' },
    { id: 'foreign', label: 'Foreign word', ref: 'magenta' },
    { id: 'narrator', label: 'Narrator', ref: 'fg-alt' },
    { id: 'charname', label: 'Character name (fallback)', ref: 'orange' },
    { id: 'you', label: 'You', ref: 'blue' },
    { id: 'date', label: 'Date / time', ref: 'blue' },
    { id: 'success', label: 'Success', ref: 'green' },
    { id: 'warning', label: 'Warning', ref: 'yellow' },
    { id: 'danger', label: 'Danger', ref: 'red' },
];

export const NEUTRAL_ROLES = {
    background: 'bg-alt',
    surface: 'bg',
    raised: 'base1',
    'surface-variant': 'base2',
    border: 'base3',
    strong: 'base4',
    'on-surface': 'fg',
    'on-background': 'fg',
    muted: 'grey',
};

// Message/markup colours not already named by a core role. Each default
// reuses a palette key a core role already proves readable (fg via
// on-surface, grey via muted, fg-alt via narrator, and the accent keys via
// link/charname/success/scene/you/date/foreign/danger), so none of these
// introduce a new contrast obligation.
export const MESSAGE_ROLES = {
    quotes: 'fg',
    parentheses: 'magenta',
    brackets: 'red',
    emphasis: 'blue',
    entities: 'yellow',
    director: 'orange',
    context_investigation: 'fg-alt',
    information: 'grey',
};

// Every key `plugins/vuetify.js` defines today that isn't already named
// above (muted, narrator, director, context_investigation).
export const LEGACY_ROLES = {
    primary: 'orange',
    secondary: 'yellow',
    delete: 'red',
    cancel: 'grey',
    normal: 'grey',
    mutedheader: 'grey',
    mutedbg: 'base1',
    unsaved: 'yellow',
    favorite: 'yellow',

    highlight1: 'blue',
    highlight2: 'magenta',
    highlight3: 'green',
    highlight4: 'red',
    highlight5: 'yellow',
    highlight6: 'orange',
    highlight7: 'teal',

    subdued1: { pal: 'blue', darken: 0.45 },
    subdued2: { pal: 'magenta', darken: 0.45 },
    subdued3: { pal: 'green', darken: 0.45 },
    subdued4: { pal: 'red', darken: 0.45 },
    subdued5: { pal: 'yellow', darken: 0.45 },
    subdued6: { pal: 'orange', darken: 0.45 },
    subdued7: { pal: 'teal', darken: 0.45 },

    persona: 'magenta',
    dirty: 'yellow',
    instructions: 'orange',

    enabled: 'green',
    disabled: 'red',

    nodeeditorbg: 'bg-alt',
    core_node: 'base4',
    core_node_selected: 'base4',
    template_node: 'orange',
    template_node_selected: 'orange',
    scene_node: 'magenta',
    scene_node_selected: 'magenta',

    character: 'fg',
    time: 'yellow',
    play_audio: 'yellow',
    avatar_border: 'base2',
    card_border: 'base2',
    defaultBadge: 'orange',

    dchat_msg_director: 'orange',
    dchat_msg_user: 'magenta',
    dchat_msg_action_result: 'orange',
    dchat_msg_loading: 'orange',
    dchat_msg_compaction: 'grey',
    dchat_msg_code: 'orange',

    hchat_msg_help: 'blue',
    hchat_msg_user: 'magenta',
    hchat_msg_doc_result: 'blue',

    cornflowerblue: 'blue',
};

const coreRolesAsMap = Object.fromEntries(CORE_ROLES.map(({ id, ref }) => [id, ref]));

export const ALL_ROLES = {
    ...coreRolesAsMap,
    ...NEUTRAL_ROLES,
    ...MESSAGE_ROLES,
    ...LEGACY_ROLES,
};

// Roles used to render text, checked for 4.5:1 contrast against every
// surface (see Global Constraints). `subdued1`-`7` are darkened accents,
// not text, and are intentionally excluded.
export const TEXT_ROLES = [
    'on-surface', 'muted',
    'narrator', 'link', 'scene', 'foreign', 'charname', 'you', 'date',
    'success', 'warning', 'danger',
    ...Object.keys(MESSAGE_ROLES),
    'highlight1', 'highlight2', 'highlight3', 'highlight4', 'highlight5', 'highlight6', 'highlight7',
];
