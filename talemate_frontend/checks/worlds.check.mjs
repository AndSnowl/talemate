// Node-only checks for the world screens' pure logic: wire dates
// (src/components/worlds/worldDates.js) and the Pinia store's message
// handling (src/stores/worlds.js). No Vue app, no test framework — run
// directly with `node checks/worlds.check.mjs` (see
// tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

import { createPinia, setActivePinia } from 'pinia';

import { dateOf, dateParts, ageAt, formatDate, spanLabel } from '../src/components/worlds/worldDates.js';
import { useWorldsStore } from '../src/stores/worlds.js';

let passed = 0;
const failures = [];

function check(name, fn) {
    try {
        fn();
        passed += 1;
    } catch (err) {
        failures.push({ name, err });
    }
}

// --- dates -----------------------------------------------------------------

check('dateOf matches WorldDate.of instants', () => {
    // values from talemate.world.dates.WorldDate.of
    assert.deepEqual(dateOf(1), { instant: 0, precision: 'year' });
    assert.deepEqual(dateOf(5), { instant: 126230400, precision: 'year' });
    assert.deepEqual(dateOf(314), { instant: 9877248000, precision: 'year' });
    assert.deepEqual(dateOf(312, 3), { instant: 9819273600, precision: 'month' });
    assert.deepEqual(dateOf(312, 3, 9), { instant: 9819964800, precision: 'day' });
});

check('dateParts round-trips dateOf', () => {
    assert.deepEqual(dateParts(dateOf(312, 3, 9)), { year: 312, month: 3, day: 9 });
    assert.deepEqual(dateParts(dateOf(42)), { year: 42, month: 1, day: 1 });
});

check('ageAt counts whole years, before the birthday too', () => {
    assert.equal(ageAt(dateOf(290), dateOf(310)), 20);
    assert.equal(ageAt(dateOf(290, 6, 10), dateOf(310, 6, 9)), 19);
    assert.equal(ageAt(dateOf(290, 6, 10), dateOf(310, 6, 10)), 20);
});

check('formatDate prefers the label, else formats like Calendar.format', () => {
    const calendar = {
        month_names: ['January', 'February', 'March', 'April', 'May', 'June', 'July',
            'August', 'September', 'October', 'November', 'December'],
        eras: [{ name: 'After the Reckoning', abbreviation: 'AR', start_year: 300 }],
    };
    assert.equal(formatDate(calendar, { ...dateOf(312), label: 'given' }), 'given');
    assert.equal(formatDate(calendar, dateOf(312)), '13 AR');
    assert.equal(formatDate(calendar, dateOf(312, 3)), 'March 13 AR');
    assert.equal(formatDate(calendar, dateOf(299)), '299');
    assert.equal(formatDate(null, null), '');
});

check('spanLabel', () => {
    const label = (year) => ({ ...dateOf(year), label: String(year) });
    assert.equal(spanLabel(null, null, null), 'always');
    assert.equal(spanLabel(null, label(304), null), '304 →');
    assert.equal(spanLabel(null, label(305), label(316)), '305 → 316');
    assert.equal(spanLabel(null, null, label(316)), '→ 316');
});

// --- the store ---------------------------------------------------------------

function freshStore() {
    setActivePinia(createPinia());
    const store = useWorldsStore();
    const sent = [];
    store.connect((message) => sent.push(message));
    return { store, sent };
}

const reply = (action, data, extra = {}) => ({ type: 'worlds', action, data, ...extra });
const WORLD = { id: 'w1', name: 'Vael', path: '/worlds/w1', calendar: {}, present: dateOf(1000), now: dateOf(1000) };

check('connect lists the worlds', () => {
    const { sent } = freshStore();
    assert.deepEqual(sent, [{ type: 'worlds', action: 'list_worlds' }]);
});

check('opening a world lists its things and scenes', () => {
    const { store, sent } = freshStore();
    store.openWorld('/worlds/w1');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'open_world', path: '/worlds/w1' });
    assert.equal(store.pending.open_world, true);
    sent.length = 0;
    store.handleMessage(reply('open_world', WORLD));
    assert.equal(store.currentWorld.name, 'Vael');
    assert.deepEqual(store.pending, {});
    assert.deepEqual(sent.map((m) => m.kind || m.action), ['character', 'place', 'lore', 'list_scenes']);
    store.handleMessage(reply('list_things', { kind: 'place', things: [{ id: 'p1', kind: 'place', name: 'Sallowford' }] }));
    assert.equal(store.things.place[0].name, 'Sallowford');
    assert.deepEqual(store.things.character, []);
});

check('opening another world clears a pending preview (it gets no reply)', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('character', 'a ferryman');
    store.regenerateProse();
    assert.equal(store.previewPending, true);
    store.openWorld('/worlds/w2');
    assert.equal(store.previewPending, false);
    assert.equal(store.previewRequest, null);
    assert.equal(store.preview, null);
    // a stray reply for the cancelled preview is dropped
    store.handleMessage(reply('preview_thing', { name: 'Oskar' }));
    assert.equal(store.preview, null);
    store.previewThing('character', 'a ferryman');
    store.handleMessage(reply('open_world', { ...WORLD, id: 'w2' }));
    assert.equal(store.previewPending, false);
    assert.equal(store.currentWorld.id, 'w2');
});

check('a preview, then accept, opens the new thing', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('character', 'a ferryman', { born: dateOf(270) });
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'preview_thing', kind: 'character', prompt: 'a ferryman', fields: { born: dateOf(270) },
    });
    const preview = { kind: 'character', prompt: 'a ferryman', fields: {}, name: 'Oskar', facts: [], prose: {} };
    store.handleMessage(reply('preview_thing', preview));
    assert.equal(store.previewPending, false);
    assert.equal(store.preview.name, 'Oskar');

    store.acceptPreview({ name: 'Oskar Dell' });
    assert.equal(sent.at(-1).preview.name, 'Oskar Dell');
    store.handleMessage(reply('accept_preview', { id: 't1', kind: 'character', name: 'Oskar Dell' }));
    assert.equal(store.preview, null);
    assert.equal(store.selectedThingId, 't1');
    assert.equal(store.thing.name, 'Oskar Dell');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'list_things', kind: 'character' });
});

check('a failed preview shows its message', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('lore', 'a treaty');
    store.handleMessage({ type: 'worlds', action: 'preview_failed', message: 'no facts' });
    assert.equal(store.previewPending, false);
    assert.equal(store.previewError, 'no facts');
});

check('edits carry the viewing date and replace the thing', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('t1', dateOf(310));
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_thing', id: 't1', at: dateOf(310) });
    store.addFact('appearance', 'A scar.', dateOf(316));
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'add_fact', thing_id: 't1', at: dateOf(310),
        category: 'appearance', text: 'A scar.', valid_from: dateOf(316), valid_until: null,
    });
    assert.equal(store.pending.add_fact, true);
    store.handleMessage(reply('add_fact', { id: 't1', kind: 'character', facts: [{ text: 'A scar.' }] }));
    assert.equal(store.thing.facts[0].text, 'A scar.');
    assert.deepEqual(store.pending, {});
    // another thing's reply doesn't replace the page
    store.handleMessage(reply('get_thing', { id: 't2' }));
    assert.equal(store.thing.id, 't1');
});

check('prose_updated refetches the thing at its date', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('t1', dateOf(310));
    store.regenerateProse();
    assert.equal(store.proseRegenerating, 't1');
    store.handleMessage(reply('prose_updated', { id: 't1' }));
    assert.equal(store.proseRegenerating, null);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_thing', id: 't1', at: dateOf(310) });
});

check('an error stops every spinner', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('lore', 'a treaty');
    store.openThing('t1');
    store.addFact('general', 'x');
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'Error during add_fact: nope' } });
    assert.equal(store.error, 'Error during add_fact: nope');
    assert.deepEqual(store.pending, {});
    assert.equal(store.previewPending, false);
});

check('a disconnect forgets the open world', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.handleMessage(reply('list_worlds', { worlds: [WORLD] }));
    store.disconnected();
    assert.equal(store.currentWorld, null);
    assert.equal(store.worlds.length, 1);
    assert.deepEqual(store.things.character, []);
});

check('other routers are ignored', () => {
    const { store } = freshStore();
    store.handleMessage({ type: 'scene_status', data: {} });
    store.handleMessage({ type: 'worlds', action: 'list_worlds', data: { worlds: [WORLD] } });
    assert.equal(store.worlds.length, 1);
});

if (failures.length) {
    for (const { name, err } of failures) {
        console.error(`FAIL ${name}\n  ${err.message}`);
    }
    console.error(`${failures.length} failed, ${passed} passed`);
    process.exit(1);
}
console.log(`ok ${passed} worlds checks passed`);
