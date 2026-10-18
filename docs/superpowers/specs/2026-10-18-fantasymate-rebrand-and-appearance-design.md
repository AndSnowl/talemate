# Fantasymate: rebrand and appearance

Date: 2026-10-18
Mockups: https://claude.ai/artifact/LqRTBAiCE7hYS4sA7mMxaF (the "Appearance: palette + roles"
artboard is the agreed look of the settings page; every artboard shows the gruvbox dark default)

## Why

The owner is hard-forking Talemate into **fantasymate**, a tool aimed at fantasy roleplay in one
growing world rather than a general scene runner. This design covers the first two of three
projects:

1. **Rebrand.** The app shows the new name.
2. **Appearance.** Warm colours by default (gruvbox dark) instead of the current cold purple and
   grey, a set of classic presets including colour-vision presets, and themes of your own.
3. **World first** (later, its own design): the world becomes the top level, scenes take place in
   a world, and a world inbox reviews what scenes want to change. See "Later" at the end.

Projects 1 and 2 go first and together. That way the screens project 3 adds are built on theme
colours from the start and never need restyling.

**Do not start building until the cultures work in progress on `feature/cultures-story` is
finished and merged.** That work is editing some of the same Vue files.

## Goals

- Every place a user sees the product name says "fantasymate".
- The app looks warm by default: gruvbox dark.
- The user can switch between presets: gruvbox dark, gruvbox light, nord, solarized dark,
  solarized light, monokai, and three colour-vision presets (red–green safe, blue–yellow safe,
  high contrast).
- The user can make a theme of their own by duplicating any preset and editing it.
- A theme change recolours the **whole** app: the app bars, drawers, cards, dialogs, the node
  editor, the director and help chats, and the scene messages.

## Non-goals

- No rename inside the code. The Python package, the `talemate` module paths, the config file and
  its folder, the websocket message names, the CLI and the scene file format all keep their
  Talemate names, so fixes from upstream Talemate still merge cleanly. (The owner's decision.)
- No new logo artwork. A text wordmark stands in until there is one.
- No layout or navigation changes. The Worlds / World / Story / Scene / Inbox tabs and the Tools
  menu belong to project 3.
- No per-scene themes.

## Anti-goals (would count as failure even if it works)

- A theme switch that leaves parts of the app in the old dark grey or purple because a component
  still sets its own colour.
- Text that becomes unreadable under some preset. Under every built-in preset, every role used
  for text (body text, `fg-alt`, `grey`, and the story roles `narrator`, `link`, `scene`,
  `foreign`, `charname`, `you`, `date`, `success`, `warning`, `danger`) must meet 4.5:1
  against the surface it is drawn on. My call: this means some presets, mostly the light ones,
  will drift from their original hex values.
- Breaking existing users' message colour settings.

## Part 1: rebrand (visual only)

Change what a person sees:

- The browser tab title and favicon (`talemate_frontend/index.html`, the public assets).
- The top bar and the logo backdrop shown when no scene is loaded (`TalemateApp.vue`, `.backdrop`).
- Text in the UI that names the product: the home screen, the onboarding wizard, the "What's new"
  panel, the help chat's self-description, the about and version display, and the settings pages.
- The docs site title, the docs landing page, and the getting-started pages. My call: the rest of
  the docs (about 245 pages mention Talemate) stay as they are for now, because those are the
  files most likely to conflict with upstream changes. A later pass can rename them all once.

Leave code identifiers, file names, component names (`TalemateApp.vue` stays), log names, config
keys, and anything sent over the websocket alone.

The wordmark is "fantasymate", lower case, set in Alegreya Bold, coloured with the theme's
`link` role (gruvbox yellow by default). This is my call and matches the mockups.

One open line for the builder: the prompts sent to the AI sometimes name Talemate (for example
in the help agent). Rename only where the user would read the name back in the UI. Prompts that
only steer the AI stay as they are.

## Part 2: appearance

### The model (the owner's choice, after Doom Emacs themes)

There are two layers:

1. **Palette.** A fixed list of named colours. Each theme sets its own value for each name:

   `bg`, `bg-alt`, `base1`, `base2`, `base3`, `base4`, `fg`, `fg-alt`, `grey`,
   `red`, `orange`, `yellow`, `green`, `teal`, `blue`, `magenta`

   `bg` is the main surface and `bg-alt` the deepest one (the page behind cards). `base1` to
   `base4` run from just above `bg` to a strong border or disabled colour. `fg` is body text,
   `fg-alt` secondary text, and `grey` muted text.

2. **Roles.** Named purposes in the UI, each pointing at a palette name. The core roles, with
   their defaults:

   | Role       | Used for                                  | Default   |
   |------------|-------------------------------------------|-----------|
   | `accent`   | primary buttons, the active tab, focus    | `orange`  |
   | `link`     | links and world things                    | `yellow`  |
   | `scene`    | things that exist only in this scene      | `teal`    |
   | `foreign`  | foreign-word highlights (cultures)        | `magenta` |
   | `narrator` | narrator messages                         | `fg-alt`  |
   | `charname` | fallback for character names (see below)  | `orange`  |
   | `you`      | the player character's lines              | `blue`    |
   | `date`     | in-world dates and time messages          | `blue`    |
   | `success`  | success, enabled, approve                 | `green`   |
   | `warning`  | warnings, unsaved, needs review           | `yellow`  |
   | `danger`   | delete, errors, disabled, reject          | `red`     |

   Every colour key the app uses today (the full list in `talemate_frontend/src/plugins/vuetify.js`:
   `primary`, `secondary`, `highlight1`–`7`, `subdued1`–`7`, the message colours, the node editor
   colours, `dchat_*`, `hchat_*`, `card_border` and so on) becomes a role with a default palette
   name. The builder picks those defaults so the app looks like gruvbox dark under the gruvbox
   dark preset. Keep the existing key names as the role names where they exist, so components
   keep working, and add the new roles above. A role can also point at a darkened or lightened
   palette colour (as Doom's `doom-darken` does), if the builder needs that for the `subdued*` set.

**Character colours (the owner's choice).** Each character keeps a colour of its own, so names
stay told apart, but that colour comes from the palette, so it follows the theme and stays
readable. Each character resolves to one of the accent palette names (`red`, `orange`,
`yellow`, `green`, `teal`, `blue`, `magenta`). Today a character's colour is a hex stored in
the scene file (`Character.color`, picked from `talemate/util/colors.py`) and sent as
`character_colors`. My call: the stored value stays, and the frontend maps it to the nearest
palette name at render time, the same remap-at-render rule as the node colours below. A
character with no stored colour gets a palette name from a stable hash of its name. `charname`
is the fallback when neither works. The mapping must stay the same across sessions, so a
character doesn't change colour on reload.

A **preset** is a full palette plus any roles it remaps. Most presets remap none. The
colour-vision presets remap a few roles as well as using their own colours.

### Built-in presets

| Preset                 | Source                                                         |
|------------------------|----------------------------------------------------------------|
| Gruvbox Dark (default) | gruvbox dark, medium contrast                                  |
| Gruvbox Light          | gruvbox light                                                  |
| Nord                   | nord                                                           |
| Solarized Dark         | solarized; `fg` raised to base2 so body text passes 4.5:1      |
| Solarized Light        | solarized light                                                |
| Monokai                | monokai                                                        |
| Warm, red–green safe   | gruvbox surfaces with Okabe–Ito accents; `success` and `scene` → `blue`, `danger` → vermilion `red` |
| Warm, blue–yellow safe | gruvbox; `link` and `warning` → `orange`, `date` → `magenta`, `you` → `teal` |
| Warm, high contrast    | darker surfaces, brighter text and stronger borders            |

The mockup's Appearance artboard holds a hex value for every palette name in every preset. Start
from those values and tune them by eye. The contrast rule in the anti-goals takes priority over
fidelity to the original schemes.

Light presets are full themes. There is no separate light/dark switch. Each preset says whether it
is light or dark, so Vuetify's `dark` flag and anything else that depends on it can follow.

### Your own themes

- **Duplicate** any preset (built-in or your own) to make a new theme, then rename it.
- In your own theme you can edit any palette colour (a hex field and a colour picker) and point
  any role at a different palette name. Built-in presets are read-only, so you duplicate one to
  change it.
- **Export** a theme to a JSON file, and **import** one. My call: the file holds the name,
  light/dark, the palette, and only the role overrides.
- Your own themes and the chosen theme are saved in the app config, next to the existing
  `appearance` settings (`src/talemate/config/schema.py`, class `Appearance`). They are app-wide,
  not per scene.

### The settings page

It goes under **Settings → Appearance** as a new first page, "Theme", ahead of the existing
"Messages" and "Visuals" pages. The layout follows the mockup:

- On the left, a preset list in three groups: Presets, Colour vision, Yours. Each entry shows four
  small swatches. At the bottom, "Duplicate current as new".
- A palette strip: one swatch per palette name. Clicking a swatch selects it for editing and shows
  which roles use it.
- A roles list: each role with its colour and a dropdown of palette names.
- A live preview: a small story excerpt plus tabs, a badge and buttons, drawn with the current
  roles. The app should also recolour live while you edit, using the existing
  `appearance-preview` mechanism in `AppSettings.vue`.

### Message colours (the existing "Messages" page)

Today each message type has an optional hex `color` (`SceneAppearance` in `schema.py`, defaults in
`talemate_frontend/src/utils/messageColors.js`). This folds into the theme like so:

- Each message type's **default** colour becomes a role (`narrator`, `charname`, `date` and
  the rest), so it follows the theme.
- Existing configs already hold the old default hex values, because the Messages page wrote
  them in (`hydrateMarkupStyle` in `AppConfigAppearanceScene.vue` saves, for example, `#FFFFFF`
  for quotes). My call: when the config loads, a saved colour that equals the old default for
  its type counts as unset, so it follows the theme. Only colours the user really chose stay
  fixed. That rule can be a load-time check, so no file rewrite is needed.
- The per-type `color` setting stays. It can hold a palette name (it follows the theme) or a hex
  value (it doesn't), and is empty by default. Saved hex values keep working, so no setting
  migration is needed.
- My call: the colour picker on the Messages page lists the palette names first, then a custom
  hex choice.
- Italic, bold, show/hide and override settings are unchanged.
- The black preview card on that page (`AppConfigAppearanceScene.vue`) uses the theme's `bg`
  instead.

### Groundwork: components must take colours from the theme

Today 51 components set colours directly (`grey-darken-3`, `bg-grey-darken-4`, `color="black"`,
raw hex values, and so on). Before switching themes can work, each of those must use a theme
colour or role instead. This is the bulk of the work. Suggested order:

1. Build the theme engine: palette, roles, presets and Vuetify theme generation, with the
   current look reproduced as the gruvbox dark default.
2. Sweep the components, worst offenders first. The ones the user sees most: the app bars, the
   home screen, scene messages, the world editor, and dialogs.
3. The settings page, your own themes, and import and export.
4. The remaining presets and a contrast check across all of them.

Colours that come from data rather than from `.vue` files are in scope too: node colours set in
the backend (`node_color`, `title_color` in about 77 files and in saved node modules), the
litegraph canvas colours in `utils/litegraphUtils.js` and `commentNode.js`, the hex values in
`utils/sceneMessageRenderer.js`, and the colour names agents send in `message.data.color`. My
call: these are remapped **in the frontend at render time**, from the known values to roles or
palette names, and stored backend values stay unchanged so upstream merges stay clean. Hex values
in frontend JS files are swept like the components.

A simple check the builder can automate: a grep that fails on Vuetify colour-scale names
(`grey-darken-*`, `blue-lighten-*` and the like) and raw hex values in `.vue` and frontend `.js` files outside the
theme module. An allow-list covers genuine exceptions.

## Left to the builder

- How the theme is applied to Vuetify: generate a Vuetify theme object per preset, or register
  one theme and overwrite its colours at runtime.
- The exact default palette name for each existing colour key.
- Whether a few CSS variables (for example `--fm-bg`) are also exposed for plain CSS.
- The tests. Tests for the theme engine are pure logic: resolving roles, applying overrides,
  import and export round trips. Component sweeps need a visual check by the owner in the browser.

## Later: project 3, world first (not part of this design)

What the owner agreed in the brainstorm. It gets its own design after this one ships:

- The home screen lists **worlds** first. Each card shows the world's most recent scenes.
  Scenes without a world (older Talemate scenes) have their own place there until moved.
- A **World tab** that works with no scene loaded. It holds characters, cultures, places,
  objects, magic, gods, factions, generic entries, the map, the calendar and **world history**,
  all linked to each other (a place has an owner, a character has a culture).
- A **scene** is created inside a world. It keeps what scenes have today (its own characters,
  entries and scene history), with categories that match the world's, and it brings in world
  entities rather than copying them.
- Scene things stay in the scene unless they're **promoted**. The AI suggests promotions to the
  inbox (the ancient artifact, not the gate guard), and the user can promote anything from any
  scene at any time.
- A **world inbox** for every proposed change to the world: additions, edits, world history and
  culture reviews (it absorbs the existing culture review). Each item can be approved, edited
  then approved, rejected, or kept in the scene only.
- **Relationships are between named characters, never "you".** The player can play anyone. A
  friendship between X and Y is recorded on both, as X → Y and Y → X.
- During play, the storyteller follows links from the current place to its owner, that
  character's context, and their shared history, and that steers the scene.
- Top navigation becomes **Worlds · World · Story · Scene · Inbox**. Templates, Prompts and Mods
  move into a **Tools** menu.
