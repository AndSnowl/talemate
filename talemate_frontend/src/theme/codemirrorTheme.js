// Builds CodeMirror 6 theme extensions (editor chrome + syntax
// highlighting) from a resolved theme (see engine.js's `resolveTheme`), so
// every CodeMirror instance in the app follows the active preset instead of
// a fixed `@codemirror/theme-one-dark`. Global Constraints: a theme change
// recolours the whole app, including the node editor's property/prompt
// editors and the scene-state/game-state JSON editors.
//
// Every colour here is read from `resolved` (roles for editor chrome,
// accent palette keys for syntax tokens) — never a literal hex. Lives
// under src/theme/ like the rest of the pure engine, so
// checks/themeColors.check.mjs's sweep guard (which only walks outside
// src/theme/) doesn't flag it.

import { EditorView } from '@codemirror/view';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { tags as t } from '@lezer/highlight';
import { hexToRgba } from './colorMath.js';

/**
 * Editor chrome — background, text, gutters, cursor, selection and active
 * line — as an `EditorView.theme()`. The editor box reads as a "raised"
 * panel (same role already used for code blocks elsewhere in the app, e.g.
 * DirectorConsoleChatMessageMarkdown.vue's `pre`/`code` blocks and
 * VersionMismatchAlert.vue's `bg-raised` snippets).
 */
export function editorTheme(resolved) {
    const colors = resolved.colors;
    return EditorView.theme({
        '&': {
            backgroundColor: colors.raised,
            color: colors['on-surface'],
        },
        '.cm-content': {
            caretColor: colors.accent,
        },
        '.cm-cursor, .cm-dropCursor': {
            borderLeftColor: colors.accent,
        },
        '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
            backgroundColor: hexToRgba(colors.accent, 0.25),
        },
        '.cm-activeLine': {
            // Low-opacity foreground tint, same idiom used for hover/active
            // rows elsewhere (adapts correctly under both dark and light
            // presets, unlike a fixed white/black tint).
            backgroundColor: hexToRgba(colors['on-surface'], 0.05),
        },
        '.cm-gutters': {
            backgroundColor: colors.raised,
            color: colors.muted,
            border: 'none',
        },
        '.cm-activeLineGutter': {
            backgroundColor: hexToRgba(colors['on-surface'], 0.08),
        },
    }, { dark: resolved.dark });
}

/**
 * Syntax highlighting. Code tokens aren't "danger"/"success" — they're just
 * distinct hues — so most of them map onto the resolved theme's accent
 * palette (the same `resolved.palette` keys character/node colours use),
 * not the app's semantic core roles. Structural/non-code bits (comments,
 * the default text colour, markdown links) use the matching neutral/core
 * role instead.
 */
export function highlightStyle(resolved) {
    const p = resolved.palette;
    const colors = resolved.colors;
    return HighlightStyle.define([
        {
            tag: [t.keyword, t.controlKeyword, t.moduleKeyword, t.operatorKeyword, t.definitionKeyword],
            color: p.magenta,
        },
        { tag: [t.string, t.docString, t.character, t.regexp], color: p.green },
        { tag: [t.number, t.integer, t.float], color: p.blue },
        { tag: [t.bool, t.null, t.atom], color: p.orange },
        {
            tag: [t.comment, t.lineComment, t.blockComment, t.docComment],
            color: colors.muted,
            fontStyle: 'italic',
        },
        { tag: [t.propertyName, t.attributeName], color: p.teal },
        { tag: [t.typeName, t.className, t.namespace], color: p.yellow },
        { tag: [t.variableName, t.name, t.self], color: colors['on-surface'] },
        {
            tag: [t.operator, t.punctuation, t.bracket, t.paren, t.brace, t.squareBracket, t.angleBracket],
            color: colors.muted,
        },
        { tag: t.heading, color: colors.accent, fontWeight: 'bold' },
        { tag: t.strong, fontWeight: 'bold' },
        { tag: t.emphasis, fontStyle: 'italic' },
        { tag: t.link, color: colors.link, textDecoration: 'underline' },
        { tag: t.invalid, color: colors.danger },
    ]);
}

/**
 * Both extensions together, ready to spread into a CodeMirror `extensions`
 * array in place of `oneDark`.
 */
export function themeExtensions(resolved) {
    return [editorTheme(resolved), syntaxHighlighting(highlightStyle(resolved))];
}
