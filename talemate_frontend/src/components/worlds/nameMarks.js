// Marks on cleaned names in a draft (languages 4a): what replaced what, or
// why a name is suspect. The draft's text is changed here, on the client,
// as any other edit of it; only the lists need the server.

function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// `name` as a whole word ("Sovyetsk" in "Sovyetsk's", never in
// "Sovyetskaya"), as the server's `cleaning.replace._swap`
function wordPattern(name) {
    return new RegExp(`(?<![\\p{L}\\p{N}])${escapeRegExp(name)}(?![\\p{L}\\p{N}])`, 'gu');
}

export function swapName(text, from, to) {
    return (text || '').replace(wordPattern(from), () => to);
}

// The draft's texts with `from` swapped for `to`: those it has of a page
// draft's name, facts, summary and "For other pages" rows, a fact draft's
// facts, a group draft's rows (each one's name and line).
function swapAll(edited, from, to) {
    const changes = {};
    if (edited.name != null) {
        changes.name = swapName(edited.name, from, to);
    }
    if (edited.facts) {
        changes.facts = edited.facts.map((fact) => ({ ...fact, text: swapName(fact.text, from, to) }));
    }
    if (edited.summary != null) {
        changes.summary = swapName(edited.summary, from, to);
    }
    if (edited.elsewhere) {
        changes.elsewhere = edited.elsewhere.map((row) => ({ ...row, text: swapName(row.text, from, to) }));
    }
    if (edited.rows) {
        changes.rows = edited.rows.map((row) => ({ ...row, name: swapName(row.name, from, to), line: swapName(row.line, from, to) }));
    }
    return changes;
}

// The new names with `from` swapped for `to` in them; a stub cleaning made
// that's back to its old name is dropped, and one back to the name it
// replaced forgets it did. With `add` (a suspect name replaced that no row
// had), a new row for it.
function renameRows(rows, from, to, add = null) {
    let found = false;
    const out = [];
    for (const row of rows || []) {
        const name = swapName(row.name, from, to);
        if (name === row.name) {
            out.push(row);
            continue;
        }
        found = true;
        if (row.from_cleaning && name === row.replaced) {
            continue;
        }
        const replaced = row.replaced || row.name;
        out.push({ ...row, name, replaced: name === replaced ? '' : replaced });
    }
    if (!found && add) {
        out.push(add);
    }
    return out;
}

// What a mark's action changes on the draft (`editDraft`'s changes), and
// the name to add to the world's keep list, if any; null for an action
// it doesn't know. `keep` drops the mark; `never_flag` drops it and keeps
// the name in this world from now on (4a revised: nothing is replaced;
// renaming is Name it…'s).
export function markEdit(edited, markId, action) {
    const marks = edited?.marks || [];
    const mark = marks.find((m) => m.id === markId);
    if (!mark || (action !== 'keep' && action !== 'never_flag')) {
        return null;
    }
    return { changes: { marks: marks.filter((m) => m.id !== markId) }, keep: action === 'never_flag' ? mark.name : null };
}

// `segments` with each mark's words split out as their own run, flagged
// (`flag`: the mark's id) and otherwise as they were: a plain run stays
// plain, a fresh one (a new stub) stays fresh. A linked or self run is
// left as it is.
export function markSegments(segments, marks) {
    const live = (marks || []).filter((m) => m.name);
    if (!live.length) {
        return segments;
    }
    const names = [...live].sort((a, b) => b.name.length - a.name.length);
    const pattern = new RegExp(names.map((m) => `(?<![\\p{L}\\p{N}])${escapeRegExp(m.name)}(?![\\p{L}\\p{N}])`).join('|'), 'gu');
    const byName = new Map(live.map((m) => [m.name, m]));
    return (segments || []).flatMap((segment) => {
        if (segment.ref || segment.self || segment.flag) {
            return [segment];
        }
        const out = [];
        let at = 0;
        for (const match of segment.text.matchAll(pattern)) {
            if (match.index > at) {
                out.push({ ...segment, text: segment.text.slice(at, match.index) });
            }
            const mark = byName.get(match[0]);
            out.push({ ...segment, text: match[0], flag: mark.id });
            at = match.index + match[0].length;
        }
        if (!out.length) {
            return [segment];
        }
        if (at < segment.text.length) {
            out.push({ ...segment, text: segment.text.slice(at) });
        }
        return out;
    });
}
