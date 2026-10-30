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

// The draft's texts with `from` swapped for `to`: its name, facts, summary
// and "For other pages" rows.
function swapAll(edited, from, to) {
    const changes = { name: swapName(edited.name, from, to) };
    changes.facts = (edited.facts || []).map((fact) => ({ ...fact, text: swapName(fact.text, from, to) }));
    if (edited.summary != null) {
        changes.summary = swapName(edited.summary, from, to);
    }
    changes.elsewhere = (edited.elsewhere || []).map((row) => ({ ...row, text: swapName(row.text, from, to) }));
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
// the name to add to the world's keep list, if any; null when there's
// nothing to do (no spare name left to reroll to).
//
// Actions: `reroll` (another spare name), `keep_here` (the old name back),
// `never` (that, and kept in this world from now on); on a suspect one,
// `replace` (a spare name), `keep` (the mark goes), `never_flag` (that,
// and kept in this world).
export function markEdit(edited, markId, action) {
    const marks = edited?.marks || [];
    const mark = marks.find((m) => m.id === markId);
    if (!mark) {
        return null;
    }
    const others = marks.filter((m) => m.id !== markId);
    const spares = mark.spares || [];
    if (action === 'reroll' || action === 'replace') {
        if (!spares.length) {
            return null;
        }
        const next = spares[0];
        const from = mark.name;
        const add =
            action === 'replace' ? { name: next, kind: mark.entry_kind || 'place', replaced: mark.was, from_cleaning: true } : null;
        const changed = {
            ...mark,
            kind: 'replaced',
            name: next,
            meaning: '',
            spares: action === 'reroll' ? [...spares.slice(1), from] : spares.slice(1),
        };
        return {
            changes: {
                ...swapAll(edited, from, next),
                new_names: renameRows(edited.new_names, from, next, add),
                marks: marks.map((m) => (m.id === markId ? changed : m)),
            },
            keep: null,
        };
    }
    if (action === 'keep_here' || action === 'never') {
        return {
            changes: {
                ...swapAll(edited, mark.name, mark.was),
                new_names: renameRows(edited.new_names, mark.name, mark.was),
                marks: others,
            },
            keep: action === 'never' ? mark.was : null,
        };
    }
    if (action === 'keep' || action === 'never_flag') {
        return { changes: { marks: others }, keep: action === 'never_flag' ? mark.name : null };
    }
    return null;
}

// `segments` with each mark's name split out as its own run (`mark`: its
// id, `markKind`), in plain and fresh runs; a linked or self run is left.
export function markSegments(segments, marks) {
    const live = (marks || []).filter((m) => m.name);
    if (!live.length) {
        return segments;
    }
    const names = [...live].sort((a, b) => b.name.length - a.name.length);
    const pattern = new RegExp(names.map((m) => `(?<![\\p{L}\\p{N}])${escapeRegExp(m.name)}(?![\\p{L}\\p{N}])`).join('|'), 'gu');
    const byName = new Map(live.map((m) => [m.name, m]));
    return (segments || []).flatMap((segment) => {
        if (segment.ref || segment.self || segment.mark) {
            return [segment];
        }
        const out = [];
        let at = 0;
        for (const match of segment.text.matchAll(pattern)) {
            if (match.index > at) {
                out.push({ ...segment, text: segment.text.slice(at, match.index) });
            }
            const mark = byName.get(match[0]);
            out.push({ text: match[0], ref: null, stub: false, mark: mark.id, markKind: mark.kind });
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
