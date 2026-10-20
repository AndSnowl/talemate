// Node-only checks for the world screens' pure logic: wire dates
// (src/components/worlds/worldDates.js) and the Pinia store's message
// handling (src/stores/worlds.js). No Vue app, no test framework — run
// directly with `node checks/worlds.check.mjs` (see
// tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

import { createPinia, setActivePinia } from 'pinia';

import { dateOf, dateParts, ageAt, clampDay, daysInMonth, formatDate, spanLabel } from '../src/components/worlds/worldDates.js';
import { useWorldsStore, parseWorldTarget, worldTarget } from '../src/stores/worlds.js';
import { NEW_THING, newNamesPayload, pickedId, picksPayload, promptSegments } from '../src/components/worlds/nameHighlights.js';

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

check('daysInMonth knows month lengths and leap years', () => {
    assert.equal(daysInMonth(1001, 1), 31);
    assert.equal(daysInMonth(1001, 4), 30);
    assert.equal(daysInMonth(1001, 2), 28);
    assert.equal(daysInMonth(1004, 2), 29);
    assert.equal(daysInMonth(1000, 2), 28);
    assert.equal(daysInMonth(1200, 2), 29);
    // years 1-99 aren't read as 1900-1999
    assert.equal(daysInMonth(4, 2), 29);
});

check('clampDay keeps a day inside its month', () => {
    assert.equal(clampDay(1001, 2, 31), 28);
    assert.equal(clampDay(1004, 2, 30), 29);
    assert.equal(clampDay(1001, 4, 31), 30);
    assert.equal(clampDay(1001, 1, 31), 31);
    assert.equal(clampDay(1001, 1, 0), 1);
    // nothing to clamp without a month or a day
    assert.equal(clampDay(1001, null, 31), 31);
    assert.equal(clampDay(1001, 2, null), null);
});

// --- name highlights ----------------------------------------------------------

const VOS = { id: 'vos', name: 'Maren Vos', kind: 'character' };
const HOLT = { id: 'holt', name: 'Maren Holt', kind: 'character' };
const SALLOW = { id: 'sal', name: 'Sallowford', kind: 'place' };
const PROMPT = 'Maren went from Sallowford for bleakcap; maren came back.';
const MATCHES = [
    { start: 0, end: 5, text: 'Maren', candidates: [HOLT, VOS] },
    { start: 16, end: 26, text: 'Sallowford', candidates: [SALLOW] },
    { start: 41, end: 46, text: 'maren', candidates: [HOLT, VOS] },
];

check('a name picks its best candidate until the owner picks another', () => {
    assert.equal(pickedId(MATCHES[0], {}), 'holt');
    assert.equal(pickedId(MATCHES[0], { maren: 'vos' }), 'vos');
    // a pick that isn't one of the candidates falls back to the best
    assert.equal(pickedId(MATCHES[0], { maren: 'gone' }), 'holt');
    assert.equal(pickedId(MATCHES[0], { maren: NEW_THING }), NEW_THING);
});

check('picks go out once per name, leaving out names treated as new', () => {
    assert.deepEqual(picksPayload(MATCHES, { maren: 'vos' }), { Maren: 'vos', Sallowford: 'sal' });
    assert.deepEqual(picksPayload(MATCHES, { maren: NEW_THING }), { Sallowford: 'sal' });
    assert.deepEqual(newNamesPayload(MATCHES, { maren: NEW_THING }), ['Maren']);
    assert.deepEqual(newNamesPayload(MATCHES, { maren: 'vos' }), []);
});

check('the prompt is cut into plain text, matched names and new names', () => {
    const segments = promptSegments(PROMPT, MATCHES, { sallowford: NEW_THING }, ['Bleakcap']);
    assert.deepEqual(
        segments.map((s) => [s.text, s.state || null]),
        [
            ['Maren', 'matched'],
            [' went from ', null],
            ['Sallowford', 'new'],
            [' for ', null],
            ['bleakcap', 'new'],
            ['; ', null],
            ['maren', 'matched'],
            [' came back.', null],
        ],
    );
    assert.equal(segments.map((s) => s.text).join(''), PROMPT);
    assert.deepEqual([segments[2].start, segments[2].end], [16, 26]);
    assert.equal(segments[4].match, null);
});

check('match offsets count code points, as the backend does', () => {
    const text = '🌙 Maren waits';
    const segments = promptSegments(text, [{ start: 2, end: 7, text: 'Maren', candidates: [VOS] }], {});
    assert.deepEqual(segments.map((s) => s.text), ['🌙 ', 'Maren', ' waits']);
});

check('world scene targets', () => {
    assert.equal(worldTarget('/w/a|b', 's1'), 'world:///w/a|b|s1');
    assert.deepEqual(parseWorldTarget('world:///w/a|b|s1'), { worldPath: '/w/a|b', sceneId: 's1' });
    assert.equal(parseWorldTarget('/scenes/x.json'), null);
    assert.equal(parseWorldTarget('world://nobar'), null);
    assert.equal(parseWorldTarget(null), null);
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
    assert.deepEqual(sent.map((m) => m.kind || m.action), ['character', 'place', 'lore', 'list_scenes', 'get_present']);
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

check('name matches belong to the exact text and date asked about', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.matchNames('Maren', dateOf(314));
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'match_names', text: 'Maren', at: dateOf(314) });
    store.handleMessage(reply('match_names', { text: 'Maren', at: dateOf(314), matches: [MATCHES[0]] }));
    assert.equal(store.matchesFor('Maren', dateOf(314)).length, 1);
    // for another text or date they don't apply
    assert.deepEqual(store.matchesFor('Maren went', dateOf(314)), []);
    assert.deepEqual(store.matchesFor('Maren', null), []);

    // a reply for an older text is dropped
    store.matchNames('Maren went');
    store.handleMessage(reply('match_names', { text: 'Maren', at: null, matches: [MATCHES[0]] }));
    assert.deepEqual(store.matchesFor('Maren went', null), []);
    store.handleMessage(reply('match_names', { text: 'Maren went', at: null, matches: [MATCHES[0]] }));
    assert.equal(store.matchesFor('Maren went', null).length, 1);

    // blank text asks nothing, and has no matches
    sent.length = 0;
    store.matchNames('  ');
    assert.deepEqual(sent, []);
    assert.deepEqual(store.matchesFor('  ', null), []);
});

check('a new lookup leaves no matches until its reply', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.matchNames('Maren went', null);
    store.handleMessage(reply('match_names', { text: 'Maren went', at: null, matches: [MATCHES[0]] }));
    store.matchNames('Bo Maren went', null);
    store.matchNames('Bo Maren went home', null);
    assert.deepEqual(store.matchesFor('Maren went', null), []);
    assert.deepEqual(store.matchesFor('Bo Maren went home', null), []);
});

check('a reply for an older date is dropped', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.matchNames('Maren', dateOf(310));
    store.matchNames('Maren', dateOf(320));
    store.handleMessage(reply('match_names', { text: 'Maren', at: dateOf(310), matches: [MATCHES[0]] }));
    assert.deepEqual(store.matchesFor('Maren', dateOf(320)), []);
    assert.deepEqual(store.matchesFor('Maren', dateOf(310)), []);
    // the backend echoes the date with its label; only instant and precision count
    store.handleMessage(reply('match_names', { text: 'Maren', at: { ...dateOf(320), label: '320' }, matches: [MATCHES[0]] }));
    assert.equal(store.matchesFor('Maren', dateOf(320)).length, 1);
});

check('a failed lookup leaves no stale matches', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.matchNames('Maren', null);
    store.handleMessage(reply('match_names', { text: 'Maren', at: null, matches: [MATCHES[0]] }));
    store.matchNames('Maren went', null);
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'Error during match_names: nope' } });
    assert.deepEqual(store.matchesFor('Maren went', null), []);
    assert.deepEqual(store.matchesFor('Maren', null), []);
    // a late reply for the failed request is not taken either
    store.handleMessage(reply('match_names', { text: 'Maren went', at: null, matches: [MATCHES[0]] }));
    assert.deepEqual(store.matchesFor('Maren went', null), []);
});

const SETUP = { setup: { player: { thing_id: 'vos' }, start: dateOf(314), intro: 'Fog.' }, names: { vos: 'Maren Vos' } };

check('plan, regenerate, edit and start a scene', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.planScene('Maren goes', { Maren: 'vos' }, null, dateOf(314), ['Tobin']);
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'plan_scene', prompt: 'Maren goes', picks: { Maren: 'vos' },
        new_names: ['Tobin'], player: null, start: dateOf(314),
    });
    assert.equal(store.setupPending, true);
    store.handleMessage(reply('plan_scene', SETUP));
    assert.equal(store.setupPending, false);
    assert.equal(store.sceneSetup.names.vos, 'Maren Vos');

    store.regenerateSetup();
    assert.equal(sent.at(-1).action, 'plan_scene');
    assert.equal(store.sceneSetup, null);
    store.handleMessage({ type: 'worlds', action: 'plan_failed', message: 'no reply' });
    assert.equal(store.setupError, 'no reply');
    assert.equal(store.setupPending, false);

    store.regenerateSetup();
    store.handleMessage(reply('plan_scene', SETUP));
    store.discardSetup();
    assert.equal(store.sceneSetup, null);
    assert.equal(store.setupRequest.data.prompt, 'Maren goes');

    store.regenerateSetup();
    store.handleMessage(reply('plan_scene', SETUP));
    store.startScene();
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'start_scene', setup: SETUP.setup });
    assert.equal(store.pending.start_scene, true);
    const started = { scene_id: 's9', target: 'world:///worlds/w1|s9', scene: { id: 's9' } };
    store.handleMessage(reply('start_scene', started));
    assert.deepEqual(store.startedScene, started);
    assert.equal(store.sceneSetup, null);
    assert.equal(store.setupRequest, null);
    assert.deepEqual(store.pending, {});
    assert.deepEqual(sent.slice(-2).map((m) => m.action), ['list_scenes', 'get_present']);
});

check('a failed start keeps the setup and stops its spinner', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.planScene('Maren goes');
    store.handleMessage(reply('plan_scene', SETUP));
    store.startScene();
    store.handleMessage({ type: 'worlds', action: 'start_failed', message: 'no client' });
    assert.equal(store.setupError, 'no client');
    assert.deepEqual(store.pending, {});
    assert.equal(store.sceneSetup.names.vos, 'Maren Vos');
});

check('a continue setup is not taken for a plan', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.continueScene('s1', 'Find the smuggler');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'continue_scene', scene_id: 's1', goal_prompt: 'Find the smuggler' });
    store.handleMessage(reply('plan_scene', SETUP));
    assert.equal(store.sceneSetup, null);
    store.handleMessage(reply('continue_scene', SETUP));
    assert.equal(store.sceneSetup.setup.intro, 'Fog.');
    // closing the dialog drops a late reply
    store.regenerateSetup();
    store.closeSetup();
    store.handleMessage(reply('continue_scene', SETUP));
    assert.equal(store.sceneSetup, null);
});

check('opening another world drops the setup step', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.planScene('Maren goes');
    store.openWorld('/worlds/w2');
    assert.equal(store.setupPending, false);
    assert.equal(store.setupRequest, null);
});

check('repositioning a scene replaces it in the list', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.handleMessage(reply('list_scenes', { scenes: [{ id: 's1', start: dateOf(313) }, { id: 's2', start: dateOf(300) }] }));
    store.repositionScene('s1', dateOf(320));
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'reposition_scene', scene_id: 's1', start: dateOf(320) });
    store.handleMessage(reply('reposition_scene', { id: 's1', start: dateOf(320) }));
    assert.deepEqual(store.scenes.map((scene) => scene.start), [dateOf(320), dateOf(300)]);
    assert.deepEqual(store.pending, {});
    // a moved scene can move "now"
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_present' });
});

check('listing scenes refreshes the world\'s now', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.listScenes();
    assert.deepEqual(sent.slice(-2).map((m) => m.action), ['list_scenes', 'get_present']);
    store.handleMessage(reply('get_present', { present: dateOf(1000), now: dateOf(1004) }));
    assert.deepEqual(store.currentWorld.now, dateOf(1004));
    assert.equal(store.currentWorld.name, 'Vael');
});

check('setPresent sets the open world\'s present year', () => {
    const { store, sent } = freshStore();
    store.setPresent(1200);
    assert.equal(sent.length, 1, 'no world open: nothing sent');
    store.handleMessage(reply('open_world', { ...WORLD, present: dateOf(1), now: dateOf(1) }));
    store.setPresent(1200);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'set_present', year: 1200 });
    assert.equal(store.pending.set_present, true);
    store.handleMessage(reply('set_present', { present: dateOf(1200), now: dateOf(1200) }));
    assert.deepEqual(store.currentWorld.present, dateOf(1200));
    assert.deepEqual(store.currentWorld.now, dateOf(1200));
    assert.deepEqual(store.pending, {});
});

check('an error while setting up a scene shows in its dialog', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.planScene('Maren goes');
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'No world is open' } });
    assert.equal(store.setupError, 'No world is open');
    assert.equal(store.setupPending, false);
    // and a failed start the same way
    store.planScene('Maren goes');
    store.handleMessage(reply('plan_scene', SETUP));
    store.startScene();
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'bad setup' } });
    assert.equal(store.setupError, 'bad setup');
    assert.deepEqual(store.pending, {});
});

check('an error with no setup step open stays on the page', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'boom' } });
    assert.equal(store.error, 'boom');
    assert.equal(store.setupError, null);
});

const REFERENCES = {
    facts: [{ thing_id: 't2', thing_name: 'Oskar', text: 'Owes Vasha a life-debt.' }],
    fields: [],
    scenes: [{ scene_id: 's1', name: 'The Ferryman', role: 'player' }],
};

check('delete checks the references, asks, then deletes and goes back to the list', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('t1');
    store.handleMessage(reply('get_thing', { id: 't1', kind: 'character', name: 'Vasha' }));

    store.requestDelete();
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'thing_references', id: 't1' });
    assert.equal(store.pending.thing_references, true);
    assert.equal(store.deleteCheck, null);

    store.handleMessage(reply('thing_references', { id: 't1', kind: 'character', name: 'Vasha', references: REFERENCES }));
    assert.deepEqual(store.pending, {});
    assert.equal(store.deleteCheck.name, 'Vasha');
    assert.equal(store.deleteCheck.references.scenes[0].name, 'The Ferryman');

    store.confirmDelete();
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'delete_thing', id: 't1' });
    assert.equal(store.pending.delete_thing, true);

    store.handleMessage(reply('thing_deleted', { id: 't1', kind: 'character' }));
    assert.deepEqual(store.pending, {});
    assert.equal(store.deleteCheck, null);
    assert.equal(store.selectedThingId, null);
    assert.equal(store.thing, null);
    store.handleMessage(reply('list_things', { kind: 'character', things: [] }));
    assert.deepEqual(store.things.character, []);
});

check('cancelling a delete sends nothing more', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('t1');
    store.requestDelete();
    store.handleMessage(reply('thing_references', { id: 't1', kind: 'character', name: 'Vasha', references: REFERENCES }));
    const count = sent.length;
    store.cancelDelete();
    assert.equal(store.deleteCheck, null);
    assert.equal(sent.length, count);
    assert.equal(store.selectedThingId, 't1');
});

check('a reference check for a thing no longer open is dropped', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('t1');
    store.requestDelete();
    store.openThing('t2');
    store.handleMessage(reply('thing_references', { id: 't1', kind: 'character', name: 'Vasha', references: REFERENCES }));
    assert.equal(store.deleteCheck, null);
});

check('a failed delete closes the dialog and shows the error', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('t1');
    store.requestDelete();
    store.handleMessage(reply('thing_references', { id: 't1', kind: 'character', name: 'Vasha', references: REFERENCES }));
    store.confirmDelete();
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'no such thing' } });
    assert.equal(store.deleteCheck, null);
    assert.equal(store.error, 'no such thing');
    assert.equal(store.selectedThingId, 't1');
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
