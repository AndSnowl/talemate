// World dates on the wire: `{instant, precision, label?}`, where `instant`
// is seconds since 1 January of year 1 (proleptic Gregorian, as
// `talemate.world.dates.WorldDate`) and `label` is the backend's rendering
// with the world's calendar. No Vue or `@/` imports, so the node checks
// (checks/worlds.check.mjs) can load this file.

function utcMillis(year, month = 0, day = 1) {
    // Date.UTC reads years 0-99 as 1900-1999; setUTCFullYear doesn't
    const date = new Date(Date.UTC(2000, 0, 1));
    date.setUTCFullYear(year, month, day);
    return date.getTime();
}

const EPOCH_MS = utcMillis(1);

// A date as WorldDate.of builds it: year precision, or month/day when given.
// `month` is 1-12.
export function dateOf(year, month = null, day = null) {
    let precision = 'year';
    if (month != null) {
        precision = day != null ? 'day' : 'month';
    }
    const ms = utcMillis(year, (month || 1) - 1, day || 1);
    return { instant: Math.round((ms - EPOCH_MS) / 1000), precision };
}

// The number of days in `month` (1-12) of `year`, proleptic Gregorian.
export function daysInMonth(year, month) {
    // day 0 of the next month is this month's last day
    const last = new Date(utcMillis(year, month, 0));
    return last.getUTCDate();
}

// `day` kept inside `month` of `year` (1 up to the month's length); left
// as it is when there's no month or no day to clamp.
export function clampDay(year, month, day) {
    if (!month || day == null || day === '') {
        return day;
    }
    return Math.min(Math.max(day, 1), daysInMonth(year, month));
}

// `{year, month, day}` (month 1-12) of a wire date.
export function dateParts(date) {
    const d = new Date(EPOCH_MS + date.instant * 1000);
    return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
}

// A whole-year age on `at`, for someone born on `born`.
export function ageAt(born, at) {
    const b = dateParts(born);
    const a = dateParts(at);
    let age = a.year - b.year;
    if (a.month < b.month || (a.month === b.month && a.day < b.day)) {
        age -= 1;
    }
    return age;
}

// The year label for `year` under `calendar`'s eras, as Calendar.format.
function yearLabel(calendar, year) {
    const eras = (calendar?.eras || []).filter((era) => era.start_year <= year);
    if (!eras.length) {
        return String(year);
    }
    const era = eras.reduce((a, b) => (b.start_year > a.start_year ? b : a));
    const shown = year - era.start_year + 1;
    return era.abbreviation ? `${shown} ${era.abbreviation}` : String(shown);
}

// A wire date as text: its own label when the backend sent one, else
// formatted the way Calendar.format does it.
export function formatDate(calendar, date) {
    if (!date) {
        return '';
    }
    if (date.label) {
        return date.label;
    }
    const { year, month, day } = dateParts(date);
    const yearText = yearLabel(calendar, year);
    if (date.precision === 'year') {
        return yearText;
    }
    const months = calendar?.month_names || [];
    const monthName = months[month - 1] || String(month);
    if (date.precision === 'month') {
        return `${monthName} ${yearText}`;
    }
    return `${day} ${monthName} ${yearText}`;
}

// A fact's span: "304 →", "305 → 316", "→ 316", or "always".
export function spanLabel(calendar, from, until) {
    if (!from && !until) {
        return 'always';
    }
    const start = from ? formatDate(calendar, from) : '';
    const end = until ? formatDate(calendar, until) : '';
    return `${start} → ${end}`.trim();
}
