// Scene-message color resolution.
//
// Single source of truth for the set of configurable "special" message color
// types and how their effective color/style is resolved from the user's
// appearance config, folded into the fantasymate theme (see ../theme/).
// Mirrors talemate.util.colors.SPECIAL_COLOR_NAMES on the backend — keep in
// sync.
//
// Imports from ../theme/ by relative path (not the `@/` Vite alias) so this
// module stays loadable under plain node — see checks/theme.check.mjs.

import { isHex } from '../theme/colorMath.js';
import { PALETTE_KEYS } from '../theme/palette.js';
import { currentTheme } from '../theme/store.js';

export const SPECIAL_MESSAGE_COLORS = [
  "narrator",
  "actor",
  "director",
  "time",
  "context_investigation",
  "information",
];

// Canonical default colors from before message colours followed the theme.
// Kept only to recognise old saved configs: a saved hex equal to the value
// here (any case) counts as "unset" and falls back to the type's theme
// role colour — see AppConfigAppearanceScene.vue's `hydrateMarkupStyle`,
// which used to seed these as literal defaults.
export const LEGACY_DEFAULT_COLORS = {
  narrator: "#A180AE",
  actor: "#B39DDB",
  director: "#FF5722",
  time: "#FFECB3",
  context_investigation: "#D5C0A1",
  information: "#BA8574",
  quotes: "#FFFFFF",
  parentheses: "#DB9DC2",
  brackets: "#DC5D5D",
  emphasis: "#B39DDB",
  entities: "#FFE082",
};

// Markup types are stored bare on the scene appearance config (`quotes`,
// `parentheses`, ...); message types are stored with a `_messages` suffix
// (`narrator_messages`, ...) — see src/talemate/config/schema.py's
// SceneAppearance.
const MARKUP_TYPES = new Set(["quotes", "parentheses", "brackets", "emphasis", "entities"]);

function sceneConfigKey(typ) {
  return MARKUP_TYPES.has(typ) ? typ : `${typ}_messages`;
}

// Message/markup type -> theme role. Markup types share their role's name;
// message types map onto the closest existing core/message role so they
// don't introduce new roles.
export const MESSAGE_ROLE = {
  narrator: "narrator",
  actor: "charname",
  director: "director",
  time: "date",
  context_investigation: "context_investigation",
  information: "information",
  quotes: "quotes",
  parentheses: "parentheses",
  brackets: "brackets",
  emphasis: "emphasis",
  entities: "entities",
};

export function isSpecialMessageColor(name) {
  return SPECIAL_MESSAGE_COLORS.includes(name);
}

function roleColorFor(typ, resolved) {
  const role = MESSAGE_ROLE[typ] || typ;
  return resolved?.colors?.[role];
}

// Resolve a raw stored colour value for a scene-message/markup type against
// a resolved theme (see ../theme/engine.js's `resolveTheme` /
// `themeFromConfig`; defaults to the live applied theme). This is the
// single choke point for the "counts as unset" rule — getMessageColor uses
// it directly, and sceneMessageRenderer.js's SceneTextParser uses it too
// (for every style it renders: quotes, parentheses, brackets, emphasis,
// entities, and the message type's own "default" text colour), so a saved
// palette key or legacy-default hex resolves the same way everywhere it's
// rendered, not just through getMessageColor's direct callers.
//
// `rawColor` (typically `cfg.color`) is resolved as:
//   - a palette key (exact, case-sensitive match against PALETTE_KEYS): the
//     palette's hex for that key
//   - a hex value equal (any case) to LEGACY_DEFAULT_COLORS[typ]: treated as
//     unset — the type's theme role colour
//   - any other hex value: that hex, verbatim
//   - empty/unset: the type's theme role colour
export function resolveMessageColor(typ, rawColor, resolved = currentTheme.value) {
  const roleColor = roleColorFor(typ, resolved);

  if (!rawColor) {
    return roleColor;
  }

  if (PALETTE_KEYS.includes(rawColor)) {
    return resolved?.palette?.[rawColor] ?? roleColor;
  }

  if (isHex(rawColor)) {
    const legacy = LEGACY_DEFAULT_COLORS[typ];
    if (legacy && rawColor.toLowerCase() === legacy.toLowerCase()) {
      return roleColor;
    }
    return rawColor;
  }

  return roleColor;
}

// Resolve the effective color for a scene-message type against the user's
// appearance config and a resolved theme — see `resolveMessageColor` for
// the resolution rules.
export function getMessageColor(appearanceConfig, typ, resolved = currentTheme.value) {
  const cfg = appearanceConfig?.scene?.[sceneConfigKey(typ)];
  return resolveMessageColor(typ, cfg?.color, resolved);
}

// Build an inline CSS style string (color + optional italic/bold) for a
// scene-message type from the user's appearance config.
export function getMessageStyle(appearanceConfig, typ, resolved = currentTheme.value) {
  const cfg = appearanceConfig?.scene?.[sceneConfigKey(typ)] || {};
  let styles = "";
  if (cfg.italic) styles += "font-style: italic;";
  if (cfg.bold) styles += "font-weight: bold;";
  styles += `color: ${getMessageColor(appearanceConfig, typ, resolved)};`;
  return styles;
}
