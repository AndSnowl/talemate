// Pure colour math for the theme engine: hex validation/normalisation,
// mixing, WCAG 2 contrast, and HSL hue/saturation. No Vue, no Vuetify.

const HEX6_RE = /^#[0-9a-fA-F]{6}$/;
const HEX3_RE = /^#[0-9a-fA-F]{3}$/;

/** True for a `#rrggbb` string, any case. */
export function isHex(s) {
    return typeof s === 'string' && HEX6_RE.test(s);
}

/**
 * Accepts `#rgb` or `#rrggbb` (any case) and returns a lower-case
 * `#rrggbb` string, or null if `s` is neither.
 */
export function normalizeHex(s) {
    if (typeof s !== 'string') return null;
    if (HEX6_RE.test(s)) return s.toLowerCase();
    if (HEX3_RE.test(s)) {
        const r = s[1];
        const g = s[2];
        const b = s[3];
        return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
    }
    return null;
}

function hexToRgb(hex) {
    const n = normalizeHex(hex);
    if (!n) throw new Error(`not a hex colour: ${hex}`);
    return {
        r: parseInt(n.slice(1, 3), 16),
        g: parseInt(n.slice(3, 5), 16),
        b: parseInt(n.slice(5, 7), 16),
    };
}

function rgbToHex({ r, g, b }) {
    const c = (v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0');
    return `#${c(r)}${c(g)}${c(b)}`;
}

/** Linear interpolation between two hex colours. `t=0` gives `a`, `t=1` gives `b`. */
export function mix(a, b, t) {
    const ca = hexToRgb(a);
    const cb = hexToRgb(b);
    return rgbToHex({
        r: ca.r + (cb.r - ca.r) * t,
        g: ca.g + (cb.g - ca.g) * t,
        b: ca.b + (cb.b - ca.b) * t,
    });
}

/** Darken a hex colour toward black by `t` (0..1). */
export function darken(hex, t) {
    return mix(hex, '#000000', t);
}

/** Lighten a hex colour toward white by `t` (0..1). */
export function lighten(hex, t) {
    return mix(hex, '#ffffff', t);
}

function relativeLuminance(hex) {
    const { r, g, b } = hexToRgb(hex);
    const lin = (c) => {
        const v = c / 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2 contrast ratio between two hex colours (1..21). */
export function contrastRatio(a, b) {
    const la = relativeLuminance(a);
    const lb = relativeLuminance(b);
    const lighter = Math.max(la, lb);
    const darker = Math.min(la, lb);
    return (lighter + 0.05) / (darker + 0.05);
}

function hexToHsl(hex) {
    const { r, g, b } = hexToRgb(hex);
    const rN = r / 255;
    const gN = g / 255;
    const bN = b / 255;
    const max = Math.max(rN, gN, bN);
    const min = Math.min(rN, gN, bN);
    const l = (max + min) / 2;
    const delta = max - min;
    if (delta === 0) {
        return { h: 0, s: 0, l };
    }
    const s = delta / (1 - Math.abs(2 * l - 1));
    let h;
    switch (max) {
        case rN:
            h = ((gN - bN) / delta) % 6;
            break;
        case gN:
            h = (bN - rN) / delta + 2;
            break;
        default:
            h = (rN - gN) / delta + 4;
    }
    h *= 60;
    if (h < 0) h += 360;
    return { h, s, l };
}

/** Hue of a hex colour, in degrees (0..360). Achromatic colours return 0. */
export function hueOf(hex) {
    return hexToHsl(hex).h;
}

/** HSL saturation of a hex colour (0..1). */
export function saturationOf(hex) {
    return hexToHsl(hex).s;
}
