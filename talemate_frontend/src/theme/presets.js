// Built-in theme presets. Read-only: a user who wants to change one
// duplicates it into a custom theme (see engine.js's themeFromConfig).
//
// Starting point: the mockup's Appearance artboard hex table (Global
// Constraints). Values that failed the 4.5:1 `contrast_text_roles` check
// were tuned by lightness only, keeping each colour's hue — see
// task-1-report.md for the preset/key/old/new table.

export const DEFAULT_PRESET_ID = 'gruvbox-dark';

export const BUILTIN_PRESETS = [
    {
        id: 'gruvbox-dark',
        name: 'Gruvbox Dark',
        dark: true,
        group: 'main',
        palette: {
            bg: '#282828', 'bg-alt': '#1d2021',
            base1: '#32302f', base2: '#3c3836', base3: '#504945', base4: '#7c6f64',
            fg: '#ebdbb2', 'fg-alt': '#d5c4a1', grey: '#a89984',
            red: '#fc6d5c', orange: '#fe8019', yellow: '#fabd2f', green: '#b8bb26',
            teal: '#8ec07c', blue: '#83a598', magenta: '#d3869b',
        },
        roles: {},
    },
    {
        id: 'gruvbox-light',
        name: 'Gruvbox Light',
        dark: false,
        group: 'main',
        palette: {
            bg: '#fbf1c7', 'bg-alt': '#f2e5bc',
            base1: '#ebdbb2', base2: '#d5c4a1', base3: '#bdae93', base4: '#928374',
            fg: '#3c3836', 'fg-alt': '#504945', grey: '#665c54',
            red: '#9d0006', orange: '#aa3803', yellow: '#82550e', green: '#67620c',
            teal: '#396a4c', blue: '#076678', magenta: '#8f3f71',
        },
        roles: {},
    },
    {
        id: 'nord',
        name: 'Nord',
        dark: true,
        group: 'main',
        palette: {
            bg: '#2e3440', 'bg-alt': '#272c36',
            base1: '#3b4252', base2: '#434c5e', base3: '#4c566a', base4: '#616e88',
            fg: '#eceff4', 'fg-alt': '#d8dee9', grey: '#a9b0be',
            red: '#d9a2a8', orange: '#dba493', yellow: '#ebcb8b', green: '#a3be8c',
            teal: '#8fbcbb', blue: '#99b3cd', magenta: '#c4a7bf',
        },
        roles: {},
    },
    {
        id: 'solarized-dark',
        name: 'Solarized Dark',
        dark: true,
        group: 'main',
        palette: {
            bg: '#002b36', 'bg-alt': '#00212b',
            base1: '#073642', base2: '#0a4250', base3: '#2c5966', base4: '#586e75',
            fg: '#eee8d5', 'fg-alt': '#93a1a1', grey: '#8e9e9f',
            red: '#e87b79', orange: '#ec7b4c', yellow: '#c49500', green: '#8ea300',
            teal: '#2dada3', blue: '#48a0de', magenta: '#e279ac',
        },
        roles: {},
    },
    {
        id: 'solarized-light',
        name: 'Solarized Light',
        dark: false,
        group: 'main',
        palette: {
            bg: '#fdf6e3', 'bg-alt': '#eee8d5',
            base1: '#f5efdc', base2: '#e4ddc8', base3: '#d3cbb7', base4: '#93a1a1',
            fg: '#073642', 'fg-alt': '#566b72', grey: '#586b72',
            red: '#c62421', orange: '#b44214', yellow: '#826200', green: '#5d6b00',
            teal: '#1d706a', blue: '#1d6ca2', magenta: '#bc2970',
        },
        roles: {},
    },
    {
        id: 'monokai',
        name: 'Monokai',
        dark: true,
        group: 'main',
        palette: {
            bg: '#272822', 'bg-alt': '#1e1f1c',
            base1: '#2f302a', base2: '#3e3d32', base3: '#49483e', base4: '#75715e',
            fg: '#f8f8f2', 'fg-alt': '#cfcfc2', grey: '#a59f85',
            red: '#fb6299', orange: '#fd971f', yellow: '#e6db74', green: '#a6e22e',
            teal: '#a1efe4', blue: '#66d9ef', magenta: '#ae81ff',
        },
        roles: {},
    },
    {
        id: 'cb-red-green',
        name: 'Warm, red–green safe',
        dark: true,
        group: 'vision',
        palette: {
            bg: '#282828', 'bg-alt': '#1d2021',
            base1: '#32302f', base2: '#3c3836', base3: '#504945', base4: '#7c6f64',
            fg: '#ebdbb2', 'fg-alt': '#d5c4a1', grey: '#a89984',
            red: '#fe7000', orange: '#e69f00', yellow: '#f0e442', green: '#00ad7e',
            teal: '#00ad7e', blue: '#56b4e9', magenta: '#cf80ac',
        },
        // Okabe-Ito colours: success and scene never rely on red vs green.
        roles: { success: 'blue', scene: 'blue', danger: 'red' },
    },
    {
        id: 'cb-blue-yellow',
        name: 'Warm, blue–yellow safe',
        dark: true,
        group: 'vision',
        palette: {
            bg: '#282828', 'bg-alt': '#1d2021',
            base1: '#32302f', base2: '#3c3836', base3: '#504945', base4: '#7c6f64',
            fg: '#ebdbb2', 'fg-alt': '#d5c4a1', grey: '#a89984',
            red: '#fc6d5c', orange: '#fe8019', yellow: '#fabd2f', green: '#b8bb26',
            teal: '#8ec07c', blue: '#83a598', magenta: '#f07fa8',
        },
        // World things use orange and dates use magenta: nothing relies on
        // blue vs yellow.
        roles: { link: 'orange', warning: 'orange', date: 'magenta', you: 'teal' },
    },
    {
        id: 'cb-high-contrast',
        name: 'Warm, high contrast',
        dark: true,
        group: 'vision',
        palette: {
            bg: '#141210', 'bg-alt': '#0b0a09',
            base1: '#221f1c', base2: '#3a342e', base3: '#6b6157', base4: '#a39686',
            fg: '#fff6e0', 'fg-alt': '#f2e2c0', grey: '#d4c3a6',
            red: '#ff6b57', orange: '#ffa040', yellow: '#ffd75e', green: '#d4e157',
            teal: '#9ee6b0', blue: '#9cc8ff', magenta: '#ffa3d0',
        },
        roles: {},
    },
];

const PRESETS_BY_ID = new Map(BUILTIN_PRESETS.map((p) => [p.id, p]));

export function getPreset(id) {
    return PRESETS_BY_ID.get(id);
}
