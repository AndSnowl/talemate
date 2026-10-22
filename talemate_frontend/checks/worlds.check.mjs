// Node-only checks for the world screens' pure logic: wire dates
// (src/components/worlds/worldDates.js) and the Pinia store's message
// handling (src/stores/worlds.js). No Vue app, no test framework — run
// directly with `node checks/worlds.check.mjs` (see
// tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

import { createPinia, setActivePinia } from 'pinia';

import { dateOf, dateParts, ageAt, clampDay, daysInMonth, formatDate, spanLabel } from '../src/components/worlds/worldDates.js';
import {
    akaAdded,
    akaChanged,
    akaEveryday,
    akaRemoved,
    branchKept,
    currentNameFrom,
    defaultOverrideIndex,
    heritageFromMatches,
    pageAfterDelete,
    parseWorldTarget,
    previewSegments,
    rejectableItems,
    sameParents,
    tiesPayload,
    useWorldsStore,
    worldTarget,
} from '../src/stores/worlds.js';
import {
    NEW_THING,
    factEditState,
    factLinkPayload,
    linkPayload,
    locateLinks,
    matchState,
    newNamesPayload,
    pickedId,
    picksPayload,
    promptSegments,
    refOccurrence,
    repicks,
    searchReferences,
} from '../src/components/worlds/nameHighlights.js';
import {
    STUB_KINDS,
    TOP_KINDS,
    canExpand,
    canPromote,
    drawerTypesFor,
    drawersPayload,
    expandNote,
    overrideCategory,
    partOfDrawers,
    sphereGroups,
    templateInfo,
    tieLead,
} from '../src/components/worlds/worldKinds.js';
import { formatNumber, ownMeasures, rangeText } from '../src/components/worlds/worldNumbers.js';

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

check('a suggested (partial) match is never picked unless the owner picks it', () => {
    const tsardom = { id: 'ts', name: 'Tsardom of Moscavia', kind: 'place', via: 'partial' };
    const suggested = { start: 0, end: 8, text: 'Moscavia', candidates: [tsardom], suggested: true };
    assert.equal(pickedId(suggested, {}), NEW_THING);
    assert.equal(pickedId(suggested, { moscavia: 'ts' }), 'ts');
    // left alone, it's neither a pick nor a name treated as new
    assert.deepEqual(picksPayload([suggested], {}), {});
    assert.deepEqual(newNamesPayload([suggested], {}), []);
    assert.deepEqual(picksPayload([suggested], { moscavia: 'ts' }), { Moscavia: 'ts' });
    assert.deepEqual(newNamesPayload([suggested], { moscavia: NEW_THING }), ['Moscavia']);
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

const TS_ID = 'a'.repeat(32);
const VOS_ID = 'b'.repeat(32);
const HOLT_ID = 'c'.repeat(32);

check('a suggested match shows dotted until the owner picks or turns it down', () => {
    const tsardom = { id: 'ts', name: 'Tsardom of Moscavia', kind: 'place' };
    const suggested = { start: 0, end: 8, text: 'Moscavia', candidates: [tsardom], suggested: true };
    assert.equal(matchState(suggested, {}), 'suggested');
    assert.equal(matchState(suggested, { moscavia: 'ts' }), 'matched');
    assert.equal(matchState(suggested, { moscavia: NEW_THING }), 'new');
    // a reference made by hand for the name counts as picked
    assert.equal(matchState(suggested, {}, { moscavia: { id: 'ts', text: 'Moscavia' } }), 'matched');
    assert.equal(matchState(MATCHES[0], {}), 'matched');
});

check('a reference made by hand wins over the best candidate, a re-pick over it', () => {
    const refs = { maren: { id: 'vos', text: 'Maren' } };
    assert.equal(pickedId(MATCHES[0], {}, refs), 'vos');
    assert.equal(pickedId(MATCHES[0], { maren: 'holt' }, refs), 'holt');
    assert.equal(pickedId(MATCHES[0], { maren: NEW_THING }, refs), NEW_THING);
    // any thing, not only a candidate
    assert.equal(pickedId(MATCHES[0], {}, { maren: { id: 'elsewhere', text: 'Maren' } }), 'elsewhere');
});

check('link payloads: matched names, then references no match covers', () => {
    const refs = { yelena: { id: 'yel', text: 'Yelena' }, sallowford: { id: 'other', text: 'Sallowford' } };
    assert.deepEqual(linkPayload(MATCHES, { maren: 'vos' }, refs), {
        picks: { Maren: 'vos', Sallowford: 'other', Yelena: 'yel' },
        newNames: [],
    });
    // treated as new: neither picked nor referenced
    assert.deepEqual(linkPayload(MATCHES, { sallowford: NEW_THING }, refs), {
        picks: { Maren: 'holt', Yelena: 'yel' },
        newNames: ['Sallowford'],
    });
});

check('re-picks are the candidates the owner chose by hand, once per name', () => {
    assert.deepEqual(repicks(MATCHES, {}), []);
    assert.deepEqual(repicks(MATCHES, { maren: 'vos', sallowford: NEW_THING }), [{ id: 'vos', name: 'Maren' }]);
    // a pick that isn't a candidate isn't a re-pick
    assert.deepEqual(repicks(MATCHES, { maren: 'gone' }), []);
});

check('references, unknown phrases and stubs-to-be show in the prompt', () => {
    const text = 'Sailed with Yelena past Iron Gate and Old Mill.';
    const unknown = [
        { start: 24, end: 33, text: 'Iron Gate' },
        { start: 38, end: 46, text: 'Old Mill' },
    ];
    const segments = promptSegments(text, [], {}, [], {
        refs: { yelena: { id: 'yel', text: 'Yelena' } },
        unknown,
        stubs: [{ text: 'Old Mill', kind: 'place' }],
    });
    assert.deepEqual(
        segments.map((s) => [s.text, s.state || null]),
        [
            ['Sailed with ', null],
            ['Yelena', 'matched'],
            [' past ', null],
            ['Iron Gate', 'unknown'],
            [' and ', null],
            ['Old Mill', 'stub'],
            ['.', null],
        ],
    );
    assert.equal(segments[1].ref.id, 'yel');
    assert.equal(segments[3].unknown.text, 'Iron Gate');
    // a reference the owner then treats as new isn't shown
    const dropped = promptSegments('Yelena', [], { yelena: NEW_THING }, [], { refs: { yelena: { id: 'yel', text: 'Yelena' } } });
    assert.deepEqual(dropped.map((s) => s.state || null), [null]);
});

check('a linked fact is edited as it reads, each link kept by position', () => {
    const segments = [
        { text: 'Maren', ref: VOS_ID, stub: false },
        { text: ' met Maren and ', ref: null, stub: false },
        { text: 'Maren', ref: HOLT_ID, stub: false },
        { text: ' near ', ref: null, stub: false },
        { text: 'Moscavia', ref: TS_ID, stub: true },
        { text: '.', ref: null, stub: false },
    ];
    const raw = `[[thing:${VOS_ID}|Maren]] met Maren and [[thing:${HOLT_ID}|Maren]] near [[thing:${TS_ID}|Moscavia]].`;
    const state = factEditState(segments, raw);
    assert.equal(state.text, 'Maren met Maren and Maren near Moscavia.');
    // the n-th time its words are written in the text
    assert.deepEqual(state.links, [
        { text: 'Maren', ref: VOS_ID, nth: 0 },
        { text: 'Maren', ref: HOLT_ID, nth: 2 },
        { text: 'Moscavia', ref: TS_ID, nth: 0 },
    ]);
    // a link to an ignored stub reads as plain words, but is kept
    const ignoredRaw = `Raised by [[thing:${VOS_ID}|Aldric]] near Aldric's.`;
    assert.deepEqual(factEditState([{ text: "Raised by Aldric near Aldric's.", ref: null, stub: false }], ignoredRaw, [VOS_ID]).links, [
        { text: 'Aldric', ref: VOS_ID, nth: 0 },
    ]);
    assert.deepEqual(factEditState([], 'plain', []), { text: 'plain', links: [] });
    // an ignored link with no shown words doesn't lose the ones after it
    const noShown = `[[thing:${HOLT_ID}]] met [[thing:${VOS_ID}|Aldric]].`;
    assert.deepEqual(factEditState([{ text: 'Old Holt met Aldric.', ref: null, stub: false }], noShown, [HOLT_ID, VOS_ID]).links, [
        { text: 'Aldric', ref: VOS_ID, nth: 0 },
    ]);
});

check('links are found again in the edited text, and sent as code-point spans', () => {
    const links = [
        { text: 'Maren', ref: VOS_ID, nth: 0 },
        { text: 'Maren', ref: HOLT_ID, nth: 2 },
        { text: 'Moscavia', ref: TS_ID, nth: 0 },
    ];
    const text = '🌙 Maren met Maren and Maren, far from Moscovy.';
    const located = locateLinks(text, links);
    assert.deepEqual(located.map((l) => [text.slice(l.start, l.end), l.ref.id, l.index]), [['Maren', VOS_ID, 0], ['Maren', HOLT_ID, 1]]);
    assert.deepEqual(factLinkPayload(text, [], {}, {}, links), {
        picks: {},
        newNames: [],
        spans: [
            { start: 2, end: 7, ref: VOS_ID },
            { start: 22, end: 27, ref: HOLT_ID },
        ],
    });
    // whole words only
    assert.deepEqual(locateLinks('Marenhall', [{ text: 'Maren', ref: VOS_ID, nth: 0 }]), []);
});

check("a pick on a plain name leaves the links of the same words theirs", () => {
    const links = [
        { text: 'Maren', ref: VOS_ID, nth: 0 },
        { text: 'Maren', ref: HOLT_ID, nth: 1 },
    ];
    const text = 'Maren rowed with Maren and Maren.';
    const matches = [0, 17, 27].map((start) => ({ start, end: start + 5, text: 'Maren', candidates: [HOLT, VOS] }));
    assert.deepEqual(factLinkPayload(text, matches, { maren: 'vos' }, {}, links), {
        picks: { Maren: 'vos' },
        newNames: [],
        spans: [
            { start: 0, end: 5, ref: VOS_ID },
            { start: 17, end: 22, ref: HOLT_ID },
        ],
    });
    // a link re-picked, or treated as new (kept plain: a null ref),
    // changes that link alone
    const changed = [{ ...links[0], ref: 'x' }, { ...links[1], ref: NEW_THING }];
    assert.deepEqual(factLinkPayload(text, matches, {}, {}, changed), {
        picks: { Maren: 'holt' },
        newNames: [],
        spans: [
            { start: 0, end: 5, ref: 'x' },
            { start: 17, end: 22, ref: null },
        ],
    });
});

check('spans count in the very text sent', () => {
    const links = [{ text: 'Maren', ref: VOS_ID, nth: 0 }];
    const sent = '  Maren rowed.  '.trim();
    assert.deepEqual(factLinkPayload(sent, [], {}, {}, links).spans, [{ start: 0, end: 5, ref: VOS_ID }]);
});

check('existing links show as matched, a same-place match attached', () => {
    const text = 'Maren met Maren.';
    const linked = [{ start: 10, end: 15, index: 0, ref: { id: 'holt', text: 'Maren' } }];
    const matches = [
        { start: 0, end: 5, text: 'Maren', candidates: [HOLT, VOS] },
        { start: 10, end: 15, text: 'Maren', candidates: [HOLT, VOS] },
    ];
    const segments = promptSegments(text, matches, {}, [], { linked });
    assert.deepEqual(segments.map((s) => [s.text, s.state || null, s.linked ? s.ref.id : null]), [
        ['Maren', 'matched', null],
        [' met ', null, null],
        ['Maren', 'matched', 'holt'],
        ['.', null, null],
    ]);
    assert.equal(segments[2].match, matches[1]);
    assert.equal(segments[2].linkIndex, 0);
    // a link turned to new by the owner shows new; a name pick doesn't touch it
    const asNew = promptSegments(text, matches, {}, [], { linked: [{ ...linked[0], ref: { id: NEW_THING, text: 'Maren' } }] });
    assert.equal(asNew[2].state, 'new');
    assert.equal(promptSegments(text, matches, { maren: NEW_THING }, [], { linked })[2].state, 'matched');
});

check("re-pointing names the link's place among the fact's references", () => {
    const raw = `[[thing:${VOS_ID}|Maren]] met [[thing:${VOS_ID}|Maren Vos]] and [[thing:${TS_ID}]].`;
    const segments = [
        { text: 'Maren', ref: VOS_ID, stub: false },
        { text: ' met ', ref: null, stub: false },
        { text: 'Maren Vos', ref: VOS_ID, stub: false },
        { text: ' and ', ref: null, stub: false },
        { text: 'Tsardom of Moscavia', ref: TS_ID, stub: true },
        { text: '.', ref: null, stub: false },
    ];
    assert.equal(refOccurrence(raw, segments, 0), 0);
    assert.equal(refOccurrence(raw, segments, 2), 1);
    assert.equal(refOccurrence(raw, segments, 4), 2);
    assert.equal(refOccurrence(raw, segments, 1), null);
    // a reference that renders plain (an ignored stub) still counts
    const withIgnored = `[[thing:${HOLT_ID}|Aldric]] and [[thing:${VOS_ID}|Maren]].`;
    assert.equal(refOccurrence(withIgnored, [{ text: 'Aldric and ', ref: null }, { text: 'Maren', ref: VOS_ID }, { text: '.', ref: null }], 1), 1);
});

check('before the names are looked up, the owner\'s own picks still go out', () => {
    const text = 'Maren went to Sallowford.';
    assert.deepEqual(linkPayload([], { maren: 'vos', sallowford: NEW_THING, gone: 'x' }, {}, text), {
        picks: { Maren: 'vos' },
        newNames: ['Sallowford'],
    });
});

check('the reference search: names holding the query, starting ones first', () => {
    const targets = [
        { id: '1', name: 'Vasha', kind: 'character', stub: false },
        { id: '2', name: 'Vasel River', kind: 'place', stub: false },
        { id: '3', name: 'Vasilka', kind: 'place', stub: true },
        { id: '4', name: 'Old Vasel', kind: 'lore', stub: false },
    ];
    assert.deepEqual(searchReferences(targets, 'vas').map((t) => t.name), ['Vasel River', 'Vasha', 'Vasilka', 'Old Vasel']);
    assert.deepEqual(searchReferences(targets, '  '), []);
    assert.deepEqual(searchReferences(targets, 'vas', 2).map((t) => t.id), ['2', '1']);
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

// --- heritage kinds and numbers ------------------------------------------------

check('races and mixes are reached from their species, not listed at the top', () => {
    const top = TOP_KINDS.map((k) => k.kind);
    assert.ok(top.includes('species'));
    assert.ok(!top.includes('race') && !top.includes('mix'));
});

check("an override takes a category the thing's kind accepts", () => {
    assert.equal(overrideCategory('character', 'physical'), 'appearance');
    assert.equal(overrideCategory('character', 'variation'), 'appearance');
    assert.equal(overrideCategory('character', 'instinct'), 'personality');
    assert.equal(overrideCategory('character', 'origin'), 'background');
    assert.equal(overrideCategory('character', 'appearance'), 'appearance');
    // a race or mix keeps the species' category
    assert.equal(overrideCategory('race', 'instinct'), 'instinct');
    assert.equal(overrideCategory('mix', 'variation'), 'variation');
});

check('numbers show plain, ranges collapse when min and max agree', () => {
    assert.equal(formatNumber(70), '70');
    assert.equal(formatNumber(67.5), '67.5');
    assert.equal(formatNumber(66.66666), '66.7');
    assert.equal(rangeText({ min: 7, max: 9, unit: 'ft' }), '7–9 ft');
    assert.equal(rangeText({ min: 9, max: 9, unit: 'ft' }), '9 ft');
    assert.deepEqual(ownMeasures({}), []);
    assert.deepEqual(ownMeasures({ measures: [{ name: 'height' }] }), [{ name: 'height' }]);
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

// every kind's listing, as opening a world, an accept or a started scene asks
const ALL_KINDS = ['character', 'species', 'race', 'mix', 'place', 'event', 'item', 'lore', 'sphere'];
const STUBS_REQUEST = { type: 'worlds', action: 'list_stubs', include_ignored: true };

// whether `sent` asked for the stubs and every kind's listing
function listedEverything(sent) {
    assert.ok(sent.some((m) => m.action === 'list_stubs' && m.include_ignored === true));
    for (const kind of ALL_KINDS) {
        assert.ok(sent.some((m) => m.action === 'list_things' && m.kind === kind), kind);
    }
}

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
    assert.deepEqual(
        sent.map((m) => m.kind || m.action),
        [...ALL_KINDS, 'list_stubs', 'list_scenes', 'get_present'],
    );
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
    // the names its facts invented are stubs now, of any kind
    listedEverything(sent.slice(-(ALL_KINDS.length + 1)));
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

check('a heritage listing asks for list_heritage; links run species first', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    sent.length = 0;
    store.handleMessage(reply('list_things', { kind: 'place', things: [] }));
    assert.deepEqual(sent, []);
    store.handleMessage(reply('list_things', { kind: 'race', things: [] }));
    assert.deepEqual(sent, [{ type: 'worlds', action: 'list_heritage' }]);
    store.handleMessage(reply('list_heritage', {
        things: [
            { id: 'owl', kind: 'species', name: 'Owl-folk', species_ids: ['owl'] },
            { id: 'human', kind: 'species', name: 'Human', species_ids: ['human'] },
            { id: 'snowy', kind: 'race', name: 'Snowy', species_ids: ['owl'] },
            { id: 'half', kind: 'mix', name: 'Half-owl', species_ids: ['owl', 'human'] },
        ],
    }));
    const names = (id) => store.heritageLinks(id).map((link) => link.name);
    assert.deepEqual(names('snowy'), ['Owl-folk', 'Snowy']);
    assert.deepEqual(names('owl'), ['Owl-folk']);
    assert.deepEqual(names('half'), ['Owl-folk', 'Human', 'Half-owl']);
    assert.deepEqual(names('gone'), []);
    assert.deepEqual(store.heritageLinks('snowy')[0], { id: 'owl', name: 'Owl-folk' });
});

check('an override and a number edit go out as edits and replace the thing', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('vasha');
    store.overrideFact('f-eyes', 'appearance', 'Blue eyes');
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'override_fact', thing_id: 'vasha', at: null,
        overridden_fact_id: 'f-eyes', category: 'appearance', text: 'Blue eyes',
    });
    assert.equal(store.pending.override_fact, true);
    store.handleMessage(reply('override_fact', { id: 'vasha', kind: 'character', facts: [{ text: 'Blue eyes' }] }));
    assert.equal(store.thing.facts[0].text, 'Blue eyes');
    assert.deepEqual(store.pending, {});

    store.openThing('snowy');
    store.setField('lifespan', 65);
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'set_field', thing_id: 'snowy', at: null, field: 'lifespan', value: 65,
    });
    store.handleMessage(reply('set_field', { id: 'snowy', kind: 'race', fields: { lifespan: 65 } }));
    assert.equal(store.thing.fields.lifespan, 65);
    // the kind's listing is refreshed, and with it the heritage list
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'list_things', kind: 'race' });
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
    assert.deepEqual(sent.slice(-(ALL_KINDS.length + 3), -(ALL_KINDS.length + 1)).map((m) => m.action), ['list_scenes', 'get_present']);
    // the stubs the setup used are filled in now
    listedEverything(sent.slice(-(ALL_KINDS.length + 1)));
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

// --- heritage in the create box ---------------------------------------------

const HERITAGE = [
    { id: 'human', kind: 'species', name: 'Human', species_ids: ['human'] },
    { id: 'orc', kind: 'species', name: 'Orc', species_ids: ['orc'] },
    { id: 'low', kind: 'race', name: 'Lowlander', species_ids: ['human'] },
];
const named = (text, ...ids) => ({ text, start: 0, end: 0, candidates: ids.map((id) => ({ id, name: text, kind: '' })) });

check('a prompt pre-fills the heritage it names, a race over its species', () => {
    assert.equal(heritageFromMatches([named('human', 'human'), named('Lowlander', 'low')], HERITAGE), 'low');
    assert.equal(heritageFromMatches([named('orc', 'orc'), named('Lowlander', 'low')], HERITAGE), 'orc');
    // names that aren't heritage things (a character) are passed over
    assert.equal(heritageFromMatches([named('Maren', 'c1'), named('orc', 'orc')], HERITAGE), 'orc');
    assert.equal(heritageFromMatches([named('Maren', 'c1')], HERITAGE), null);
});

check('find_mix answers the parents asked about, in either order', () => {
    assert.ok(sameParents(['a', 'b'], ['b', 'a']));
    assert.ok(!sameParents(['a', 'b'], ['a', 'c']));
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.findMix(['low', 'orc']);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'find_mix', parents: ['low', 'orc'] });
    // a reply for other parents is dropped
    store.handleMessage(reply('find_mix', { parents: ['human', 'orc'], mix_id: null }));
    assert.equal(store.mixFound, null);
    store.handleMessage(reply('find_mix', { parents: ['orc', 'low'], mix_id: 'm1' }));
    assert.deepEqual(store.mixFound, { parents: ['orc', 'low'], mix_id: 'm1' });
    assert.equal(store.mixLookup, null);
});

check('a failed mix lookup stops waiting', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.findMix(['low', 'orc']);
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'no' } });
    assert.equal(store.mixLookup, null);
});

check('a mix drafted for a character is accepted without opening its page', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('mix', '', { parents: ['low', 'orc'] });
    store.handleMessage(reply('preview_thing', { kind: 'mix', prompt: '', fields: {}, name: 'Half-orc', facts: [], prose: {} }));
    store.acceptPreview({ name: 'Half-orc' }, { open: false });
    store.handleMessage(reply('accept_preview', { id: 'm1', kind: 'mix', name: 'Half-orc' }));
    assert.deepEqual(store.accepted, { id: 'm1', kind: 'mix', name: 'Half-orc' });
    assert.equal(store.selectedThingId, null);
    assert.equal(store.previewRequest, null);
    listedEverything(sent.slice(-(ALL_KINDS.length + 1)));
    // the next accept opens its page again
    store.previewThing('character', 'a smith', { heritage: 'm1' });
    store.handleMessage(reply('preview_thing', { kind: 'character', prompt: 'a smith', fields: {}, name: 'Gorra', facts: [], prose: {} }));
    store.acceptPreview({ name: 'Gorra' });
    store.handleMessage(reply('accept_preview', { id: 'c1', kind: 'character', name: 'Gorra' }));
    assert.equal(store.selectedThingId, 'c1');
});

check('cancelling a preview forgets its request', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('mix', '', { parents: ['low', 'orc'] });
    store.cancelPreview();
    assert.equal(store.previewRequest, null);
    assert.equal(store.previewPending, false);
    store.handleMessage(reply('preview_thing', { name: 'late' }));
    assert.equal(store.preview, null);
});

check('marking an inherited fact overridden moves it to one own fact', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('character', 'a smith', { heritage: 'low' });
    const preview = {
        kind: 'character', prompt: 'a smith', fields: {}, name: 'Gorra', prose: {},
        facts: [
            { category: 'personality', text: 'Quick to anger.', overrides: [] },
            { category: 'appearance', text: 'Tall.', overrides: [] },
            { category: 'appearance', text: 'Green skin.', overrides: [] },
        ],
        inherited: [{ fact_id: 'f1', source: 'Lowlander', source_id: 'low', category: 'physical', text: 'Short.' }],
    };
    store.handleMessage(reply('preview_thing', preview));
    // a physical fact is overridden by the first appearance fact
    assert.equal(defaultOverrideIndex(store.preview, preview.inherited[0]), 1);
    assert.equal(defaultOverrideIndex({ ...preview, facts: [] }, preview.inherited[0]), -1);
    store.setPreviewOverride('f1', 1);
    assert.deepEqual(store.preview.facts.map((f) => f.overrides), [[], ['f1'], []]);
    store.setPreviewOverride('f1', 2);
    assert.deepEqual(store.preview.facts.map((f) => f.overrides), [[], [], ['f1']]);
    store.acceptPreview({ name: 'Gorra' });
    assert.deepEqual(sent.at(-1).preview.facts[2].overrides, ['f1']);
    store.setPreviewOverride('f1', null);
    assert.deepEqual(store.preview.facts.map((f) => f.overrides), [[], [], []]);
});

check('one prose section regenerates on its own', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('t1');
    store.regenerateProse('personality');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'regenerate_prose', id: 't1', at: null, section: 'personality' });
    assert.equal(store.proseRegenerating, 't1');
    assert.equal(store.proseRegeneratingSection, 'personality');
    store.handleMessage(reply('prose_updated', { id: 't1', section: 'personality' }));
    assert.equal(store.proseRegenerating, null);
    assert.equal(store.proseRegeneratingSection, null);
    // the whole-page button still regenerates every section
    store.regenerateProse();
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'regenerate_prose', id: 't1', at: null });
    assert.equal(store.proseRegeneratingSection, null);
});

const NAME_TIMELINE = [
    { date: null, change: 'field', field: 'name', value: 'Lowlander' },
    { date: dateOf(380), change: 'fact_start', field: null, value: null },
    { date: dateOf(400), change: 'field', field: 'name', value: 'Dalesfolk' },
];

check('a rename corrects the name in effect at the viewing date', () => {
    assert.equal(currentNameFrom(NAME_TIMELINE, null).instant, dateOf(400).instant);
    assert.equal(currentNameFrom(NAME_TIMELINE, dateOf(350)), null);
    assert.equal(currentNameFrom([], null), null);

    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('r1', dateOf(350));
    store.handleMessage(reply('get_thing', { id: 'r1', kind: 'race', name: 'Lowlander', at: dateOf(350), timeline: NAME_TIMELINE }));
    store.renameThing('Vale-folk');
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'set_field', thing_id: 'r1', at: dateOf(350), field: 'name', value: 'Vale-folk', valid_from: null,
    });
    store.viewThingAt(null);
    store.handleMessage(reply('get_thing', { id: 'r1', kind: 'race', name: 'Dalesfolk', at: null, timeline: NAME_TIMELINE }));
    store.renameThing('Dales');
    const { label: _label, ...from } = dateOf(400);
    assert.deepEqual(sent.at(-1).valid_from, { instant: from.instant, precision: from.precision });
    // the reply refreshes the kind's list, and with it the heritage list
    store.handleMessage(reply('set_field', { id: 'r1', kind: 'race', name: 'Dales' }));
    assert.equal(store.thing.name, 'Dales');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'list_things', kind: 'race' });
    store.handleMessage(reply('list_things', { kind: 'race', things: [{ id: 'r1', kind: 'race', name: 'Dales' }] }));
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'list_heritage' });
});

const DELETE_HERITAGE = [
    { id: 'hum', kind: 'species', name: 'Human', species_ids: ['hum'] },
    { id: 'orc', kind: 'species', name: 'Orc', species_ids: ['orc'] },
    { id: 'low', kind: 'race', name: 'Lowlander', species_ids: ['hum'] },
    { id: 'mix', kind: 'mix', name: 'Half-orc', species_ids: ['hum', 'orc'] },
];

check('after a delete, a race or mix goes back to its species page', () => {
    const race = { id: 'low', kind: 'race', fields: { species: 'hum' } };
    const mix = { id: 'mix', kind: 'mix', fields: { parents: ['low', 'orc'] } };
    assert.equal(pageAfterDelete(race, DELETE_HERITAGE, null), 'hum');
    // the species page the mix was opened from, if it's one of the mix's
    assert.equal(pageAfterDelete(mix, DELETE_HERITAGE, 'orc'), 'orc');
    // else its first parent's species
    assert.equal(pageAfterDelete(mix, DELETE_HERITAGE, 'c1'), 'hum');
    assert.equal(pageAfterDelete(mix, DELETE_HERITAGE, null), 'hum');
    assert.equal(pageAfterDelete({ ...mix, fields: { parents: ['orc', 'low'] } }, DELETE_HERITAGE, null), 'orc');
    // other kinds go back to the list
    assert.equal(pageAfterDelete({ id: 'c1', kind: 'character', fields: {} }, DELETE_HERITAGE, 'hum'), null);
    assert.equal(pageAfterDelete({ id: 'hum', kind: 'species', fields: {} }, DELETE_HERITAGE, null), null);

    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.handleMessage(reply('list_heritage', { things: DELETE_HERITAGE }));
    store.openThing('orc');
    store.openThing('mix');
    store.handleMessage(reply('get_thing', mix));
    store.requestDelete();
    store.handleMessage(reply('thing_references', { id: 'mix', kind: 'mix', name: 'Half-orc', references: REFERENCES }));
    store.confirmDelete();
    store.handleMessage(reply('thing_deleted', { id: 'mix', kind: 'mix' }));
    assert.equal(store.selectedThingId, 'orc');
    assert.equal(store.deleteCheck, null);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_thing', id: 'orc', at: null });
});

check('other routers are ignored', () => {
    const { store } = freshStore();
    store.handleMessage({ type: 'scene_status', data: {} });
    store.handleMessage({ type: 'worlds', action: 'list_worlds', data: { worlds: [WORLD] } });
    assert.equal(store.worlds.length, 1);
});

// --- connections: kinds, other names, preview names, stubs ------------------

check('events and items are kinds of their own; a culture stub waits', () => {
    const top = TOP_KINDS.map((k) => k.kind);
    assert.ok(top.includes('event') && top.includes('item'));
    assert.ok(STUB_KINDS.includes('culture') && !STUB_KINDS.includes('race'));
    assert.equal(canExpand('culture'), false);
    assert.equal(canExpand('place'), true);
    assert.equal(expandNote('culture'), 'Cultures arrive in the next slice');
    assert.equal(expandNote('place'), null);
});

check('a race or mix stub is made from its species page, not expanded', () => {
    // its top-level create box has no species (or parents) to give it
    for (const kind of ['race', 'mix']) {
        assert.equal(canExpand(kind), false, kind);
        assert.equal(expandNote(kind), 'Make it from its species page');
    }
    for (const kind of STUB_KINDS.filter((k) => k !== 'culture')) {
        assert.equal(canExpand(kind), true, kind);
    }
});

check('other names: add, retag, the everyday pick and remove', () => {
    const owls = { name: 'Moscavian Owls', tag: 'common', everyday: false };
    let aka = akaAdded([], '  Moscavian   Owls ', 'common', 'Owl-folk');
    assert.deepEqual(aka, [owls]);
    // a blank name, a name it has, or the main name: unchanged
    assert.equal(akaAdded(aka, ' ', 'common'), aka);
    assert.equal(akaAdded(aka, 'moscavian owls', 'proper'), aka);
    assert.equal(akaAdded(aka, 'owl-folk', 'proper', 'Owl-folk'), aka);
    aka = akaAdded(aka, 'Strigine Folk', 'proper');
    // only a common name can be everyday, and only one
    assert.deepEqual(akaEveryday(aka, 1), aka.map((entry) => ({ ...entry, everyday: false })));
    aka = akaEveryday(aka, 0);
    assert.deepEqual(aka.map((entry) => entry.everyday), [true, false]);
    aka = akaAdded(aka, 'Owls', 'common');
    aka = akaEveryday(aka, 2);
    assert.deepEqual(aka.map((entry) => entry.everyday), [false, false, true]);
    assert.deepEqual(akaEveryday(aka, 2).map((entry) => entry.everyday), [false, false, false]);
    // tagged proper, it's no longer the everyday one
    const retagged = akaChanged(aka, 2, { tag: 'proper' });
    assert.deepEqual(retagged[2], { name: 'Owls', tag: 'proper', everyday: false });
    assert.equal(akaChanged(aka, 2, { name: 'strigine folk' }), aka);
    assert.equal(akaChanged(aka, 2, { name: '  ' }), aka);
    assert.equal(akaChanged(aka, 2, { name: 'The Owls' })[2].name, 'The Owls');
    assert.deepEqual(akaRemoved(aka, 0).map((entry) => entry.name), ['Strigine Folk', 'Owls']);
    // an entry missing `everyday` (as the AI may write it) gets it
    assert.deepEqual(akaAdded([{ name: 'Owls', tag: 'common' }], 'Strix', 'proper')[0], { name: 'Owls', tag: 'common', everyday: false });
});

check('a preview marks the names it invents, whole words only', () => {
    const names = [
        { name: 'Tsardom of Moscavia', kind: 'place', aka: [{ name: 'Moscavia', tag: 'common' }], written: [] },
        { name: 'The Night of Feathers', kind: 'event', aka: [], written: ['Night of Feathers'] },
    ];
    const text = 'Born in the Tsardom of Moscavia after the Night of Feathers; Moscavians call it Moscavia.';
    const segments = previewSegments(text, names);
    assert.equal(segments.map((s) => s.text).join(''), text);
    assert.deepEqual(
        segments.filter((s) => s.fresh).map((s) => [s.text, s.kind]),
        [['Tsardom of Moscavia', 'place'], ['Night of Feathers', 'event'], ['Moscavia', 'place']],
    );
    assert.deepEqual(previewSegments('No names here.', names), [{ text: 'No names here.', ref: null, stub: false }]);
    assert.deepEqual(previewSegments('', names), []);
});

const STUB = { id: 's1', name: 'Tsardom of Moscavia', kind: 'place', first_mentioned: { thing_id: 'owl', name: 'Owl-folk' }, mentions: 1, ignored: false };

check('ignoring a stub from another page refreshes that page, the lists and the stubs', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.handleMessage(reply('list_stubs', { stubs: [STUB] }));
    assert.deepEqual(store.stubInfo('s1'), STUB);
    assert.equal(store.stubInfo('nope'), null);
    store.openThing('owl');
    store.handleMessage(reply('get_thing', { id: 'owl', kind: 'species' }));
    sent.length = 0;
    store.ignoreStub('s1');
    assert.deepEqual(sent, [{ type: 'worlds', action: 'ignore_stub', id: 's1', ignored: true }]);
    assert.equal(store.pending.ignore_stub, true);
    store.handleMessage(reply('ignore_stub', { id: 's1', kind: 'place', stub: { ignored: true } }));
    assert.equal(store.thing.id, 'owl');
    assert.deepEqual(store.pending, {});
    assert.deepEqual(sent.slice(1), [
        { type: 'worlds', action: 'get_thing', id: 'owl', at: null },
        { type: 'worlds', action: 'list_things', kind: 'place' },
        STUBS_REQUEST,
    ]);
    // on the stub's own page, the reply is the page
    store.openThing('s1');
    store.handleMessage(reply('ignore_stub', { id: 's1', kind: 'place', stub: { ignored: false } }));
    assert.deepEqual(store.thing.stub, { ignored: false });
});

check("a stub's new kind lists the old kind and the new", () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.handleMessage(reply('list_stubs', { stubs: [STUB] }));
    sent.length = 0;
    store.changeStubKind('s1', 'event');
    store.handleMessage(reply('change_stub_kind', { id: 's1', kind: 'event', stub: { ignored: false } }));
    assert.deepEqual(sent, [
        { type: 'worlds', action: 'change_stub_kind', id: 's1', kind: 'event' },
        { type: 'worlds', action: 'list_things', kind: 'place' },
        { type: 'worlds', action: 'list_things', kind: 'event' },
        STUBS_REQUEST,
    ]);
    // a culture stub isn't listed with the kinds
    sent.length = 0;
    store.handleMessage(reply('list_stubs', { stubs: [{ ...STUB, kind: 'event' }] }));
    store.handleMessage(reply('change_stub_kind', { id: 's1', kind: 'culture', stub: { ignored: false } }));
    assert.deepEqual(sent, [{ type: 'worlds', action: 'list_things', kind: 'event' }, STUBS_REQUEST]);
});

check('expanding a stub previews with its id, and accepting ends it', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('owl');
    store.expandStub(STUB);
    assert.equal(store.selectedThingId, null);
    assert.deepEqual(store.expanding, { id: 's1', kind: 'place', name: 'Tsardom of Moscavia' });
    store.previewThing('place', 'Tsardom of Moscavia', {}, 's1');
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'preview_thing', kind: 'place', prompt: 'Tsardom of Moscavia', fields: {}, stub_id: 's1',
    });
    store.handleMessage(reply('preview_thing', { kind: 'place', name: 'Tsardom of Moscavia', facts: [], prose: {}, stub_id: 's1' }));
    store.regeneratePreview();
    assert.equal(sent.at(-1).stub_id, 's1');
    store.handleMessage(reply('preview_thing', { kind: 'place', name: 'Tsardom of Moscavia', facts: [], prose: {}, stub_id: 's1' }));
    store.acceptPreview();
    store.handleMessage(reply('accept_preview', { id: 's1', kind: 'place', name: 'Tsardom of Moscavia' }));
    assert.equal(store.expanding, null);
    assert.equal(store.selectedThingId, 's1');
    // a plain preview sends no stub id
    store.previewThing('place', 'a town');
    assert.equal('stub_id' in sent.at(-1), false);
});

check('expanding a stub over an unaccepted preview asks first', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('place', 'a town');
    store.handleMessage(reply('preview_thing', { kind: 'place', name: 'Kalmara', facts: [], prose: {} }));
    sent.length = 0;

    // the preview is kept, and the owner is asked
    store.expandStub(STUB);
    assert.deepEqual(store.expandAsk, { id: 's1', kind: 'place', name: 'Tsardom of Moscavia' });
    assert.equal(store.expanding, null);
    assert.equal(store.preview.name, 'Kalmara');
    assert.deepEqual(sent, []);

    // keeping it changes nothing
    store.keepPreview();
    assert.equal(store.expandAsk, null);
    assert.equal(store.preview.name, 'Kalmara');
    assert.equal(store.expanding, null);

    // discarding it expands the stub
    store.expandStub(STUB);
    store.confirmExpand();
    assert.equal(store.expandAsk, null);
    assert.equal(store.preview, null);
    assert.deepEqual(store.expanding, { id: 's1', kind: 'place', name: 'Tsardom of Moscavia' });
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'stub_suggestion', id: 's1' });

    // with no preview open, nothing is asked
    const fresh = freshStore();
    fresh.store.handleMessage(reply('open_world', WORLD));
    fresh.store.expandStub(STUB);
    assert.equal(fresh.store.expandAsk, null);
    assert.equal(fresh.store.expanding.id, 's1');
});

check('other names are written whole, and an edit re-lists the stubs', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('owl');
    const aka = [{ name: 'Moscavian Owls', tag: 'common', everyday: false }];
    store.setAka(aka);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'set_field', thing_id: 'owl', at: null, field: 'aka', value: aka });
    sent.length = 0;
    store.handleMessage(reply('set_field', { id: 'owl', kind: 'species', aka }));
    assert.deepEqual(store.thing.aka, aka);
    assert.deepEqual(sent, [STUBS_REQUEST, { type: 'worlds', action: 'list_things', kind: 'species' }]);
});

check('expanding a stub asks for its suggestion; previews carry the names', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.expandStub(STUB);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'stub_suggestion', id: 's1' });
    // a suggestion for another stub is dropped
    store.handleMessage(reply('stub_suggestion', { id: 'other', prompt: 'x', context: [] }));
    assert.equal(store.stubSuggestion, null);
    const suggestion = { id: 's1', prompt: 'Tsardom of Moscavia: the owl-folk land.', context: [['Owl-folk (species)', ['A fact.']]] };
    store.handleMessage(reply('stub_suggestion', suggestion));
    assert.deepEqual(store.stubSuggestion, suggestion);

    store.previewThing('place', 'A town in Moscavia', {}, null, {
        picks: { Moscavia: 's1' },
        newNames: ['Kalmara'],
        repicks: [{ id: 's1', name: 'Moscavia' }],
    });
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'preview_thing', kind: 'place', prompt: 'A town in Moscavia', fields: {},
        picks: { Moscavia: 's1' }, new_names: ['Kalmara'],
    });
    store.regeneratePreview();
    assert.deepEqual(sent.at(-1).picks, { Moscavia: 's1' });
    store.handleMessage(reply('preview_thing', { kind: 'place', name: 'Kalmara', facts: [], prose: {}, matching_stub_id: 'k1' }));

    // accepting into a stub; once accepted, the re-pick fetches the stub
    // to teach it the name
    sent.length = 0;
    store.acceptPreview({ name: 'Kalmara' }, { intoStub: 'k1' });
    assert.deepEqual(sent.map((m) => m.action), ['accept_preview']);
    assert.equal(sent[0].into_stub, 'k1');
    store.handleMessage(reply('accept_preview', { id: 'k1', kind: 'place', name: 'Kalmara' }));
    assert.ok(sent.some((m) => m.action === 'get_thing' && m.id === 's1' && m.at === null));
});

check('fact edits carry spans; re-pointing sends one reference', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('owl');
    store.correctFact('f1', { text: 'Maren met Maren.' }, { spans: [{ start: 0, end: 5, ref: 'vos' }] });
    assert.deepEqual(sent.at(-1).spans, [{ start: 0, end: 5, ref: 'vos' }]);
    store.repointRef('f1', 2, 'holt');
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'repoint_ref', thing_id: 'owl', at: null, fact_id: 'f1', occurrence: 2, to_id: 'holt',
    });
    store.handleMessage(reply('repoint_ref', { id: 'owl', kind: 'species', facts: [] }));
    assert.equal(store.pending.repoint_ref, undefined);
});

check('another name is added once the thing is fetched, unless it has it', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.addOtherName('s1', 'Moscavia');
    sent.length = 0;
    store.handleMessage(reply('get_thing', { id: 's1', kind: 'place', name: 'Tsardom of Moscavia', aka: [] }));
    assert.deepEqual(sent, [{
        type: 'worlds', action: 'set_field', thing_id: 's1', at: null, field: 'aka',
        value: [{ name: 'Moscavia', tag: 'common', everyday: false }],
    }]);
    assert.deepEqual(store.akaQueue, {});
    // the page of another thing stays as it was
    assert.equal(store.thing, null);

    // its main name, or a name it has, writes nothing
    store.addOtherName('s1', 'tsardom of moscavia');
    store.addOtherName('s1', 'Moscavia');
    sent.length = 0;
    store.handleMessage(reply('get_thing', {
        id: 's1', kind: 'place', name: 'Tsardom of Moscavia', aka: [{ name: 'Moscavia', tag: 'common', everyday: false }],
    }));
    assert.deepEqual(sent, []);
});

check('fact edits carry their picks and names treated as new; make_stub is an edit', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('owl');
    store.addFact('general', 'Sailed with Yelena.', null, null, { picks: { Yelena: 'y1' }, newNames: ['Sallowford'] });
    assert.deepEqual(sent.at(-1).picks, { Yelena: 'y1' });
    assert.deepEqual(sent.at(-1).new_names, ['Sallowford']);
    store.correctFact('f1', { text: 'Plain.' });
    assert.equal('picks' in sent.at(-1), false);
    store.makeStub('f1', 'Iron Gate', 'place');
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'make_stub', thing_id: 'owl', at: null, fact_id: 'f1', text: 'Iron Gate', kind: 'place',
    });
    sent.length = 0;
    store.handleMessage(reply('make_stub', { id: 'owl', kind: 'species', facts: [] }));
    assert.equal(store.thing.id, 'owl');
    assert.deepEqual(sent, [STUBS_REQUEST]);
});

check('unknown phrases belong to the exact text and date asked about', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.matchNames('Past Iron Gate.');
    store.handleMessage(reply('match_names', { text: 'Past Iron Gate.', at: null, matches: [], unknown: [{ start: 5, end: 14, text: 'Iron Gate' }] }));
    assert.deepEqual(store.unknownFor('Past Iron Gate.', null), [{ start: 5, end: 14, text: 'Iron Gate' }]);
    assert.deepEqual(store.unknownFor('Past Iron Gate', null), []);
});

check('Add reference searches entries and live stubs, not ignored ones', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.handleMessage(reply('list_things', { kind: 'character', things: [{ id: 'v', kind: 'character', name: 'Vasha' }] }));
    store.handleMessage(reply('list_things', { kind: 'place', things: [{ id: 's1', kind: 'place', name: 'Tsardom of Moscavia', stub: { ignored: false } }] }));
    store.handleMessage(reply('list_stubs', { stubs: [
        { id: 's1', name: 'Tsardom of Moscavia', kind: 'place', mentions: 1, ignored: false },
        { id: 'a1', name: 'Aldric', kind: 'character', mentions: 2, ignored: true },
    ] }));
    assert.deepEqual(store.referenceTargets.map((t) => [t.id, t.stub]).sort(), [['s1', true], ['v', false]]);
});

// --- spheres ---------------------------------------------------------------

check('the Spheres list groups by template, in template order, stubs kept in place', () => {
    const things = [
        { id: 'o1', kind: 'sphere', name: 'The Guild', template: 'order' },
        { id: 'r1', kind: 'sphere', name: 'The White Dawn', template: 'religion', stub: { ignored: false } },
        { id: 'p1', kind: 'place', name: 'Tsardom', template: 'nation' },
        { id: 'x1', kind: 'sphere', name: 'Odd', template: 'cult' },
        { id: 'n1', kind: 'sphere', name: 'Nameless', template: null },
        { id: 'r2', kind: 'sphere', name: 'The Old Faith', template: 'religion' },
    ];
    const groups = sphereGroups(things);
    assert.deepEqual(groups.map((g) => [g.template, g.label, g.things.map((t) => t.id)]), [
        ['religion', 'Religions', ['r1', 'r2']],
        ['nation', 'Nations', ['p1']],
        ['order', 'Orders', ['o1']],
        ['other', 'Other spheres', ['x1', 'n1']],
    ]);
    assert.deepEqual(groups[0].things[0].stub, { ignored: false });
    assert.deepEqual(sphereGroups(undefined), []);
    assert.equal(templateInfo('culture').agent, false);
    assert.equal(templateInfo('nation').agent, true);
    assert.equal(templateInfo(null).template, 'other');
    // spheres are a top kind, and a stub can be guessed one
    assert.ok(TOP_KINDS.some((k) => k.kind === 'sphere'));
    assert.ok(STUB_KINDS.includes('sphere') && canExpand('sphere'));
});

check('a thing may be filed only in the drawers the backend allows, and Unsorted', () => {
    const drawers = [
        { id: 'd1', type: 'beliefs', title: 'Doctrines' },
        { id: 'd2', type: 'places', title: 'Holy Sites' },
        { id: 'd3', type: 'people', title: 'People' },
        { id: 'd4', type: 'structure', title: 'Hierarchy' },
        { id: 'd5', type: 'events', title: 'Timeline' },
        { id: 'unsorted', type: 'knowledge', title: 'Unsorted' },
    ];
    assert.deepEqual(drawerTypesFor('place'), ['places']);
    assert.deepEqual(drawerTypesFor('lore'), ['practices', 'beliefs', 'knowledge', 'structure']);
    assert.deepEqual(partOfDrawers(drawers, 'lore').map((d) => d.id), ['d1', 'd4', 'unsorted']);
    assert.deepEqual(partOfDrawers(drawers, 'place').map((d) => d.id), ['d2', 'unsorted']);
    // a sphere stub has no drawers yet
    assert.deepEqual(partOfDrawers(undefined, 'lore'), [{ id: 'unsorted', title: 'Unsorted' }]);
});

check('"Make it a sphere…" is offered on lore, a place not yet a sphere and a stub', () => {
    assert.equal(canPromote({ kind: 'lore', stub: null, sphere: null }), true);
    assert.equal(canPromote({ kind: 'place', stub: null, sphere: null }), true);
    assert.equal(canPromote({ kind: 'place', stub: null, sphere: { template: 'nation' } }), false);
    assert.equal(canPromote({ kind: 'character', stub: { ignored: false }, sphere: null }), true);
    assert.equal(canPromote({ kind: 'character', stub: null, sphere: null }), false);
    assert.equal(canPromote({ kind: 'event', stub: null, sphere: null }), false);
    // a sphere stub is expanded as it is
    assert.equal(canPromote({ kind: 'sphere', stub: { ignored: false }, sphere: { template: null } }), false);
    assert.equal(canPromote(null), false);
});

check('tie lines lead with the role; payloads drop labels and Unsorted', () => {
    assert.equal(tieLead('practitioner'), 'Practitioner of');
    assert.equal(tieLead('  elder '), 'Elder of');
    assert.equal(tieLead(''), 'Of');
    const since = { ...dateOf(1010), label: '1010' };
    assert.deepEqual(
        tiesPayload([{ sphere_id: 'dawn', sphere_name: 'The White Dawn', role: 'elder', since, until: null, exceptions: [] }]),
        [{ sphere_id: 'dawn', role: 'elder', since: dateOf(1010), until: null }],
    );
    assert.deepEqual(
        drawersPayload([
            { id: 'd1', type: 'beliefs', title: 'Doctrines', inherited: false, items: [] },
            { id: 'p1', type: 'practices', title: 'Rites', inherited: true, items: [] },
            { id: 'unsorted', type: 'knowledge', title: 'Unsorted', inherited: false, items: [] },
        ]),
        [
            { id: 'd1', type: 'beliefs', title: 'Doctrines' },
            { id: 'p1', type: 'practices', title: 'Rites' },
        ],
    );
});

check('an exception can depart from any item; a branch drops what the owner unticks', () => {
    const sphere = {
        drawers: [
            { id: 'd1', items: [{ thing_id: 'c1', fact_id: null, name: 'The Council' }] },
            { id: 'd2', items: [{ thing_id: null, fact_id: 'f1', name: 'Light is purity.' }] },
        ],
    };
    assert.deepEqual(rejectableItems(sphere), [
        { title: 'The Council', value: { thing_id: 'c1' } },
        { title: 'Light is purity.', value: { fact_id: 'f1' } },
    ]);
    assert.deepEqual(rejectableItems(null), []);
    let preview = { drops: [], rejects: [] };
    preview = branchKept(preview, { thing_id: 'c1', fact_id: null }, false);
    preview = branchKept(preview, { thing_id: null, fact_id: 'f1' }, false);
    assert.deepEqual([preview.drops, preview.rejects], [['c1'], ['f1']]);
    preview = branchKept(preview, { thing_id: 'c1', fact_id: null }, true);
    assert.deepEqual([preview.drops, preview.rejects], [[], ['f1']]);
});

check('a sphere preview, then accept, opens the sphere and lists everything', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.makeSphere({ id: 'l1', kind: 'lore', name: 'The Doctrine', stub: null });
    assert.deepEqual(store.promoting, { id: 'l1', kind: 'lore', name: 'The Doctrine' });
    store.previewSphere('religion', '', {}, { promoteId: 'l1' });
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'preview_sphere', template: 'religion', prompt: '', fields: {}, promote_id: 'l1',
    });
    store.handleMessage({ type: 'worlds', action: 'preview_sphere_failed', message: 'no outline' });
    assert.equal(store.spherePreviewError, 'no outline');
    assert.equal(store.spherePreviewPending, false);
    store.regenerateSpherePreview();
    assert.equal(sent.at(-1).promote_id, 'l1');
    const preview = { kind: 'sphere', name: 'The Doctrine', template: 'religion', drawers: [], items: [], facts: [], prose: {} };
    store.handleMessage(reply('preview_sphere', preview));
    store.acceptSphere({ name: 'The Doctrine of Separation' });
    assert.equal(sent.at(-1).preview.name, 'The Doctrine of Separation');
    sent.length = 0;
    store.handleMessage(reply('accept_sphere', { id: 'l1', kind: 'sphere', name: 'The Doctrine of Separation' }));
    assert.equal(store.selectedThingId, 'l1');
    assert.equal(store.spherePreview, null);
    assert.equal(store.promoting, null);
    assert.deepEqual(store.pending, {});
    listedEverything(sent);

    // a stub is made a sphere by expanding it as one
    store.makeSphere({ id: 's2', kind: 'lore', name: 'Old Rite', stub: { ignored: false } });
    assert.deepEqual(store.expanding, { id: 's2', kind: 'sphere', name: 'Old Rite' });
    store.previewSphere('culture', 'Old Rite', {}, { stubId: 's2' });
    assert.equal(sent.at(-1).stub_id, 's2');
});

check('a branch preview stays on its parent until accepted', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('dawn');
    store.previewBranch('dawn', 'the smiths');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'preview_branch', parent_id: 'dawn', prompt: 'the smiths' });
    store.handleMessage(reply('preview_branch', { name: 'The Forge Dawn', drops: [], rejects: [], parent_items: [] }));
    store.setBranchKept({ thing_id: 'vigil', fact_id: null }, false);
    assert.deepEqual(store.branchPreview.drops, ['vigil']);
    store.acceptBranch({ name: 'The Forge Dawn' });
    assert.deepEqual(sent.at(-1).preview.drops, ['vigil']);
    store.handleMessage(reply('accept_sphere', { id: 'forge', kind: 'sphere', name: 'The Forge Dawn' }));
    assert.equal(store.branchPreview, null);
    assert.equal(store.selectedThingId, 'forge');
});

check('Fill keeps its items for the drawer asked about, then writes those kept', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('dawn');
    store.fillDrawer('dawn', 'd1');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'fill_drawer', sphere_id: 'dawn', drawer_id: 'd1' });
    // a reply for another drawer is dropped
    store.handleMessage(reply('fill_drawer', { sphere_id: 'dawn', drawer_id: 'd2', items: [{ name: 'X' }] }));
    assert.equal(store.fill.items, null);
    const items = [{ drawer_id: 'd1', name: 'Dawn Vigil', text: 'A prayer.', kind: 'lore', names: [] }];
    store.handleMessage(reply('fill_drawer', { sphere_id: 'dawn', drawer_id: 'd1', items }));
    assert.deepEqual(store.fill.items, items);
    store.acceptFill(items);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'accept_fill', sphere_id: 'dawn', drawer_id: 'd1', items });
    sent.length = 0;
    store.handleMessage(reply('accept_fill', { id: 'dawn', kind: 'sphere', name: 'The White Dawn', sphere: {} }));
    assert.equal(store.fill, null);
    assert.equal(store.thing.id, 'dawn');
    listedEverything(sent);
    // a failed Fill says why
    store.fillDrawer('dawn', 'd1');
    store.handleMessage({ type: 'worlds', action: 'fill_failed', message: 'cut off', data: { sphere_id: 'dawn', drawer_id: 'd1' } });
    assert.deepEqual([store.fill.pending, store.fill.error], [false, 'cut off']);
});

check("sphere edits answer with the thing edited; another thing's reply refreshes the page", () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('dawn');
    store.handleMessage(reply('get_thing', { id: 'dawn', kind: 'sphere', sphere: {} }));
    store.setDrawers('dawn', [{ type: 'knowledge', title: 'Key Texts' }]);
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'set_drawers', sphere_id: 'dawn', drawers: [{ type: 'knowledge', title: 'Key Texts' }], at: null,
    });
    store.handleMessage(reply('set_drawers', { id: 'dawn', kind: 'sphere', name: 'The White Dawn', sphere: { drawers: [] } }));
    assert.deepEqual(store.thing.sphere, { drawers: [] });
    assert.deepEqual(store.pending, {});

    // "+ Add" files another thing here: the page is fetched again
    store.setPartOf('council', 'dawn', 'd1');
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'set_part_of', thing_id: 'council', sphere_id: 'dawn', drawer_id: 'd1', at: null,
    });
    sent.length = 0;
    store.handleMessage(reply('set_part_of', { id: 'council', kind: 'lore', name: 'The Council' }));
    assert.equal(store.thing.id, 'dawn');
    assert.deepEqual(sent[0], { type: 'worlds', action: 'get_thing', id: 'dawn', at: null });
    // taking a thing out sends no drawer
    store.setPartOf('council', null);
    assert.equal('drawer_id' in sent.at(-1), false);

    store.endItem('dawn', { thing_id: 'dance', fact_id: null }, dateOf(1015), 'church');
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'end_item', sphere_id: 'dawn', thing_id: 'dance', at: dateOf(1015), by: 'church',
    });
    store.endItem('dawn', { thing_id: null, fact_id: 'f1' }, dateOf(1015));
    assert.equal(sent.at(-1).fact_id, 'f1');
    assert.equal(sent.at(-1).by, null);
});

check('a tie added from the sphere waits for its character, then writes the whole list', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('dawn');
    store.addTie('vasha', { sphere_id: 'dawn', role: 'elder', since: dateOf(1012) });
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_thing', id: 'vasha', at: null });
    const old = { sphere_id: 'post', sphere_name: 'Post', role: 'courier', since: { ...dateOf(1009), label: '1009' }, until: null, exceptions: [] };
    store.handleMessage(reply('get_thing', { id: 'vasha', kind: 'character', ties: [old] }));
    assert.deepEqual(sent.at(-1), {
        type: 'worlds',
        action: 'set_ties',
        character_id: 'vasha',
        ties: [
            { sphere_id: 'post', role: 'courier', since: dateOf(1009), until: null },
            { sphere_id: 'dawn', role: 'elder', since: dateOf(1012), until: null },
        ],
        at: null,
    });
    assert.deepEqual(store.tieQueue, {});
    assert.equal(store.pending.set_ties, true);
    store.handleMessage(reply('set_ties', { id: 'vasha', kind: 'character' }));
    assert.deepEqual(store.pending, {});
});

check('a fetched sphere is kept for editors; exceptions go out with what they reject', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('vasha');
    store.fetchSphere('dawn');
    store.handleMessage(reply('get_thing', { id: 'dawn', kind: 'sphere', sphere: { drawers: [] } }));
    assert.deepEqual(store.sphereInfo.dawn.sphere, { drawers: [] });
    assert.equal(store.thing, null);
    store.addException('vasha', 'dawn', 'Skips the vigil.', { thing_id: 'vigil' });
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'add_exception', character_id: 'vasha', sphere_id: 'dawn',
        text: 'Skips the vigil.', rejects: { thing_id: 'vigil' }, at: null,
    });
});

check("a character preview's ties can be dropped whole or one exception at a time", () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('character', 'an elder');
    const ties = [
        { sphere_id: 'dawn', sphere: 'The White Dawn', role: 'elder', exceptions: [{ text: 'a' }, { text: 'b' }] },
        { sphere_id: 'post', sphere: 'Post', role: 'courier', exceptions: [] },
    ];
    store.handleMessage(reply('preview_thing', { kind: 'character', name: 'Marfa', facts: [], prose: {}, ties }));
    store.dropPreviewException(0, 1);
    store.dropPreviewTie(1);
    assert.deepEqual(store.preview.ties, [{ ...ties[0], exceptions: [{ text: 'a' }] }]);
    // the reply's own list is untouched
    assert.equal(ties[0].exceptions.length, 2);
});

check('a failed sphere request stops its spinners', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewSphere('order', 'smiths');
    store.fillDrawer('dawn', 'd1');
    store.addTie('vasha', { sphere_id: 'dawn', role: '' });
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'not a sphere' } });
    assert.equal(store.spherePreviewPending, false);
    assert.deepEqual([store.fill.pending, store.fill.error], [false, 'not a sphere']);
    assert.deepEqual(store.tieQueue, {});
    assert.equal(store.error, 'not a sphere');
});

if (failures.length) {
    for (const { name, err } of failures) {
        console.error(`FAIL ${name}\n  ${err.message}`);
    }
    console.error(`${failures.length} failed, ${passed} passed`);
    process.exit(1);
}
console.log(`ok ${passed} worlds checks passed`);
