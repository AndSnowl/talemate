// Display helpers for a species, race or mix's numbers (lifespan, adult
// age and measures; `talemate.world.heritage.Numbers`). No `@/` imports:
// the node checks (checks/worlds.check.mjs) load this file.

// A number as shown: whole numbers plain, others to one decimal (a mix's
// averaged values can be fractions).
export function formatNumber(value) {
    return Number.isInteger(value) ? String(value) : String(Math.round(value * 10) / 10);
}

// A measure's range, e.g. "7–9 ft", or "9 ft" when min and max agree.
export function rangeText(range) {
    const low = formatNumber(range.min);
    const high = formatNumber(range.max);
    return `${low === high ? low : `${low}–${high}`} ${range.unit}`;
}

// The thing's own measures, as stored (`fields.measures`): a list of
// `{name, min, max, unit}`, empty when unset.
export function ownMeasures(fields) {
    return Array.isArray(fields?.measures) ? fields.measures : [];
}
