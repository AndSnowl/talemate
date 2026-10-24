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
    countsLine,
    currentNameFrom,
    defaultOverrideIndex,
    disagreements,
    elsewhereGroups,
    elsewhereSame,
    heritageFromMatches,
    historyBack,
    historyPushed,
    lineDates,
    listedFacts,
    nameKey,
    pageAfterDelete,
    parseWorldTarget,
    previewCounts,
    previewSegments,
    repointedNote,
    moveInEdit,
    rowChanged,
    rowsTicked,
    samePage,
    sameParents,
    useWorldsStore,
    worldTarget,
} from '../src/stores/worlds.js';
import {
    NEW_THING,
    factEditState,
    factFormValid,
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
    EXISTENCE,
    LISTED_KINDS,
    STUB_KINDS,
    TOP_KINDS,
    actsInWorld,
    canExpand,
    existenceOf,
    escapeCloses,
    expandLabel,
    expandNote,
    overrideCategory,
    offerSummary,
    otherKindNote,
} from '../src/components/worlds/worldKinds.js';
import {
    GROUP_SHOWN,
    connectedCount,
    dropTag,
    filingDates,
    groupKey,
    groupView,
    kindList,
    normaliseTag,
    tagChoices,
    tagHeading,
    timelineShown,
} from '../src/components/worlds/entryPage.js';
import { formatNumber, ownMeasures, rangeText } from '../src/components/worlds/worldNumbers.js';
import {
    acceptable,
    addFiling,
    alsoHere,
    categoryFor,
    changeFiling,
    changeKind,
    changeNewName,
    copyFactTo,
    filingKey,
    removeFiling,
    draftFactRows,
    freshSegments,
    holdFact,
    moveFactTo,
    namedSegments,
    rebaseDraft,
    removeFact,
    retarget,
    settleRepeat,
    tickFact,
    tickFileInto,
    tickMoveHere,
    versionRows,
} from '../src/components/worlds/draftPage.js';

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

// A draft as `preview_thing` answers it: the page of `preview` (its own
// facts as drafted rows) plus the preview, its key and versions.
function draftOf(preview, { key = null, version = 1, count = null } = {}) {
    const facts = (preview.facts || []).map((fact, index) => ({
        fact_id: null, draft: true, index, category: fact.category, text: fact.text, rendered: fact.text,
        segments: [{ text: fact.text, ref: null, stub: false }], ticked: fact.ticked !== false, repeat_of: fact.repeat_of || null,
    }));
    const versions = Array.from({ length: count || version }, (_, i) => ({ version: i + 1, name: preview.name, prompt: preview.prompt || '' }));
    return {
        id: preview.stub_id || null, draft: true, kind: preview.kind, name: preview.name, facts, in: [], entry_timeline: [],
        preview, draft_key: key || (preview.stub_id ? `stub:${preview.stub_id}` : `new:${preview.kind}:${nameKey(preview.name || '')}`), version, versions,
    };
}

// every kind's listing, as opening a world, an accept or a started scene asks
const ALL_KINDS = ['character', 'species', 'race', 'mix', 'place', 'event', 'item', 'lore', 'being'];
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
        [...ALL_KINDS, 'list_stubs', 'list_tags', 'list_scenes', 'get_present'],
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
    store.handleMessage(reply('preview_thing', draftOf(preview)));
    assert.equal(store.previewPending, false);
    assert.equal(store.preview.name, 'Oskar');

    store.acceptPreview({ name: 'Oskar Dell' });
    assert.equal(sent.at(-1).preview.name, 'Oskar Dell');
    // the draft goes with it, and stays until the server answers
    assert.equal(sent.at(-1).draft_key, 'new:character:oskar');
    assert.equal(store.draft.accepting, true);
    store.handleMessage(reply('accept_preview', { id: 't1', kind: 'character', name: 'Oskar Dell' }));
    assert.equal(store.preview, null);
    assert.equal(store.selectedThingId, 't1');
    assert.equal(store.thing.name, 'Oskar Dell');
    // the names its facts invented are stubs now, of any kind
    listedEverything(sent.slice(-(ALL_KINDS.length + 1)));
});

check("accepts send the draft as the owner left it: ticks, elsewhere facts and Could move here rows", () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('lore', 'a doctrine');
    const preview = {
        kind: 'lore',
        prompt: 'a doctrine',
        fields: {},
        name: 'The Divine Right',
        facts: [
            { category: 'general', text: 'A copy.', ticked: false, repeat_of: { fact_id: 'f1' } },
            { category: 'general', text: 'Fresh.', ticked: true, repeat_of: null },
        ],
        elsewhere: [
            { target_id: 't1', target_name: 'Tsardom', category: 'about', text: 'About it.', ticked: true },
            { target_id: null, target_name: 'White Talon', new: { name: 'White Talon', kind: 'lore', same_as: [{ thing_id: 'wt' }], same_target_id: null }, category: 'general', text: 'Trains.', ticked: true },
        ],
        move_here: [
            { fact_id: 'm1', from_id: 'tsardom', text: 'Its law code.', ticked: true },
            { fact_id: 'm2', from_id: 'tsardom', text: 'Its army.', ticked: false },
        ],
        prose: {},
    };
    store.handleMessage(reply('preview_thing', draftOf(preview)));
    // the owner's edits: the repeat ticked in, the Tsardom row unticked,
    // the stub row is the White Talon the world has
    store.editPreview('create', { facts: rowsTicked(store.preview.facts, [0], true) });
    store.editPreview('create', { elsewhere: rowsTicked(store.preview.elsewhere, [0], false) });
    store.editPreview('create', { elsewhere: elsewhereSame(store.preview.elsewhere, 'the White Talon', 'wt') });
    store.acceptPreview({ name: 'The Divine Right of the Tsar' }, { sameTargetId: 'church' });
    const request = sent.at(-1);
    assert.equal(request.action, 'accept_preview');
    assert.equal(request.same_target_id, 'church');
    const out = request.preview;
    assert.equal(out.name, 'The Divine Right of the Tsar');
    assert.deepEqual(out.facts.map((fact) => fact.ticked), [true, true]);
    assert.deepEqual(out.elsewhere.map((row) => row.ticked), [false, true]);
    assert.equal(out.elsewhere[1].new.same_target_id, 'wt');
    assert.deepEqual(out.move_here.map((row) => row.ticked), [true, false]);
    // a refusal keeps the draft as the owner left it; then no same target,
    // no key
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'no' } });
    assert.equal(store.draft.accepting, false);
    assert.equal(store.preview.name, 'The Divine Right');
    store.acceptPreview();
    assert.equal('same_target_id' in sent.at(-1), false);
    // the reply's notes are kept to show
    store.handleMessage(reply('accept_preview', { id: 'dr', kind: 'lore', name: 'The Divine Right', notes: ['Kalmara was deleted, so its fact is left out'] }));
    assert.deepEqual(store.notes, { action: 'accept_preview', notes: ['Kalmara was deleted, so its fact is left out'] });
    store.clearNotes();
    assert.equal(store.notes, null);

});

check('a same-thing offer: a stub by its flag, never by its words; its summary without the kind', () => {
    const lake = { thing_id: 'a', name: 'Ashenmere', kind: 'place', line: 'Ashenmere (place): A stub of land juts into the lake.', stub: false };
    const candle = { thing_id: 'c', name: 'Old Candle', kind: 'item', line: 'Old Candle (item; part of Church, in its Rites drawer): a stub of wax.', stub: false };
    const shore = { thing_id: 's', name: 'Ashenmere Shore', kind: 'place', line: 'Ashenmere Shore (place; stub)', stub: true };
    const relic = { thing_id: 'r', name: 'Relic', kind: 'item', line: 'Relic (item; stub)', stub: true };
    const river = { thing_id: 'k', name: 'Khorol', kind: 'place', line: 'Khorol (place, river; in Velikoye (runs through)): A wide river.', stub: false };
    assert.equal(offerSummary(lake), 'A stub of land juts into the lake.');
    assert.equal(offerSummary(candle), 'part of Church, in its Rites drawer: a stub of wax.');
    // its tag goes with its kind; where it's filed stays
    assert.equal(offerSummary(river), 'in Velikoye (runs through): A wide river.');
    assert.equal(offerSummary(relic), '');
    assert.equal(offerSummary(shore), '');
    assert.equal(offerSummary({ name: 'X', kind: 'lore', line: 'Something else' }), 'Something else');
});

check('a stub row onto another kind says so (ruling C34)', () => {
    assert.equal(otherKindNote('place', { kind: 'lore' }), '(a lore)');
    assert.equal(otherKindNote('lore', { kind: 'item' }), '(an item)');
    assert.equal(otherKindNote('place', { kind: 'place' }), '');
    assert.equal(otherKindNote(null, { kind: 'lore' }), '');
    assert.equal(otherKindNote('place', {}), '');
});

check('the Accept line counts what an accept writes', () => {
    const preview = {
        facts: [{ ticked: true }, { ticked: true }, { ticked: false, repeat_of: {} }],
        elsewhere: [
            { ticked: true, target_id: 'm' },
            { ticked: false, target_id: 't' },
            { ticked: true, new: { name: 'White Talon', same_target_id: null } },
            { ticked: true, new: { name: 'the White Talon', same_target_id: null } },
            { ticked: true, new: { name: 'Conclave', same_target_id: 'c1' } },
            { ticked: false, new: { name: 'Frosted Wing', same_target_id: null } },
        ],
        new_names: [{ name: "The Tsar's Army" }, { name: 'Synod', same_target_id: 's1' }],
        move_here: [{ ticked: true }, { ticked: false }],
    };
    const counts = previewCounts(preview);
    assert.deepEqual(counts, { facts: 2, elsewhere: 4, stubs: 2, movedIn: 1 });
    assert.equal(countsLine(counts), 'writes 2 facts here, 4 elsewhere, 2 new stubs, moves 1 in');
    const one = { facts: 1, elsewhere: 0, stubs: 1, movedIn: 0 };
    assert.equal(countsLine(one, 'Ashenmere'), 'writes 1 fact onto Ashenmere, 1 new stub');
    assert.equal(countsLine(previewCounts({})), 'writes 0 facts here');
});

check('elsewhere rows group by entry, untick together, and a stub row answers "same as"', () => {
    const rows = [
        { target_id: 'm', target_name: 'Moskov', ticked: true },
        { target_id: 't', target_name: 'Tsardom', ticked: true },
        { target_id: null, target_name: 'White Talon', new: { name: 'White Talon' }, ticked: true },
        { target_id: 't', target_name: 'Tsardom', ticked: true },
        { target_id: null, target_name: 'The White Talon', new: { name: 'The White Talon' }, ticked: true },
    ];
    const groups = elsewhereGroups(rows);
    assert.deepEqual(groups.map((group) => [group.name, group.rows]), [['Moskov', [0]], ['Tsardom', [1, 3]], ['White Talon', [2, 4]]]);
    assert.equal(groups[2].new.name, 'White Talon');
    assert.deepEqual(rowsTicked(rows, groups[1].rows, false).map((row) => row.ticked), [true, false, true, false, true]);
    assert.deepEqual(rowChanged(rows, 0, { category: 'description' })[0], { ...rows[0], category: 'description' });
    const same = elsewhereSame(rows, 'white talon', 'wt');
    assert.deepEqual(same.map((row) => row.new?.same_target_id ?? null), [null, null, 'wt', null, 'wt']);
    assert.equal(nameKey('The  White Talon'), 'white talon');
});

check('timeline lines: an ended one shows its span; the flags are the server\'s', () => {
    const label = (year) => ({ ...dateOf(year), label: String(year) });
    assert.equal(lineDates(null, { date: label(900), until: label(1010) }), '900–1010');
    assert.equal(lineDates(null, { date: label(947), until: null }), '947');
    assert.equal(lineDates(null, { date: null, until: null }), '—');
    // an ended fact disagrees with nothing (ruling C22): the server leaves
    // it out of `disagrees_with`, and the page shows what it says
    const lines = [
        { fact_id: 'a', date: label(217), until: null, disagrees_with: ['b'] },
        { fact_id: 'b', date: label(312), until: null, disagrees_with: ['a', 'gone'] },
        { fact_id: 'c', date: label(300), until: label(1026), disagrees_with: [] },
    ];
    const found = disagreements(lines);
    assert.deepEqual(Object.keys(found), ['a', 'b']);
    // a line the timeline doesn't show is no flag
    assert.deepEqual(found.b.map((line) => line.fact_id), ['a']);
    assert.deepEqual(disagreements([{ ...lines[0], disagrees_with: [] }]), {});
});

check('Esc closes an inline editor, unless it closes a picker or popover in it first', () => {
    const inPicker = { target: { closest: (selector) => (selector.includes('.v-select') ? {} : null) } };
    const plain = { target: { closest: () => null } };
    assert.equal(escapeCloses(inPicker), false);
    // no open overlay (no document in node): it closes
    assert.equal(escapeCloses(plain), true);
    assert.equal(escapeCloses(null), true);
});

check('a merge: its preview, the owner\'s picks, and the merged entry opened', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('caves');
    store.handleMessage(reply('get_thing', { id: 'caves', kind: 'place', name: 'The Ashenmere Caves' }));
    store.previewMerge('caves', 'ash');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'preview_merge', from_id: 'caves', into_id: 'ash' });
    const preview = {
        from_id: 'caves',
        into_id: 'ash',
        from_name: 'The Ashenmere Caves',
        into_name: 'Ashenmere',
        names: ['Ashenmere', 'The Ashenmere Caves'],
        facts: [
            { fact_id: 'f1', side: 'from', text: 'Garrison.', ticked: true, repeat_of: null },
            { fact_id: 'f2', side: 'from', text: 'Runes.', ticked: false, repeat_of: { owner_name: 'Ashenmere' } },
            { fact_id: 'f3', side: 'into', text: 'Runes.', ticked: true, repeat_of: null },
        ],
        pairs: [{ key: 'a1:b1', a: 'a1', b: 'b1', a_text: 'x', b_text: 'y', score: 1, years: [950, 947] }, { key: 'a2:b2', a: 'a2', b: 'b2' }],
        moves: { facts: 1, links: 2 },
        notes: [],
        akas: ['the caves'],
    };
    // a stale reply (another pair) is dropped
    store.handleMessage(reply('preview_merge', { preview: { ...preview, into_id: 'other' } }));
    assert.equal(store.merge.preview, null);
    store.handleMessage(reply('preview_merge', { preview }));
    assert.deepEqual(store.merge.preview, preview);
    assert.equal(store.merge.pending, false);
    store.acceptMerge({ mainName: 'The Ashenmere Caves', keep: { 'a1:b1': 'b' }, lose: 'end', akas: [], ticked: { f2: true } });
    const request = sent.at(-1);
    assert.equal(request.action, 'accept_merge');
    assert.equal(request.main_name, 'The Ashenmere Caves');
    // every pair answered: an unanswered one keeps both
    assert.deepEqual(request.keep, { 'a1:b1': 'b', 'a2:b2': 'both' });
    assert.equal(request.lose, 'end');
    assert.deepEqual(request.akas, []);
    assert.deepEqual(request.preview.facts.map((fact) => fact.ticked), [true, true, true]);
    store.handleMessage(reply('accept_merge', {
        from_id: 'caves',
        into: { id: 'ash', kind: 'place', name: 'The Ashenmere Caves' },
        main_name: 'The Ashenmere Caves',
        links: 2,
        aka_added: ['Ashenmere'],
        facts_moved: 2,
        notes: ['one fact ended'],
    }));
    assert.equal(store.merge, null);
    assert.equal(store.selectedThingId, 'ash');
    assert.equal(store.thing.name, 'The Ashenmere Caves');
    assert.ok(store.gone.includes('caves'));
    assert.deepEqual(store.notes.notes, [
        'Merged into The Ashenmere Caves: 2 facts and 2 links moved over',
        'now also known as Ashenmere',
        'one fact ended',
    ]);
    // back skips the merged-away page
    assert.equal(historyBack(store.history, (id) => store.gone.includes(id)).page?.thingId ?? null, null);
});

check('a fact moves, is held or not, and a timeline pick refreshes the page', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('dr', dateOf(1020));
    store.moveFact('f1', 'moskov');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'move_fact', fact_id: 'f1', target_id: 'moskov' });
    store.handleMessage(reply('move_fact', { fact_id: 'f9', target: { id: 'moskov', name: 'Moskov' }, notes: [] }));
    // the page it left is fetched again, as of its date
    assert.deepEqual(sent.at(-2), { type: 'worlds', action: 'get_thing', id: 'dr', at: dateOf(1020) });
    assert.deepEqual(store.notes.notes, ['Moved to Moskov']);
    assert.deepEqual(store.pending, {});

    store.setHeldBy('f2', 'church');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'set_held_by', thing_id: 'dr', at: dateOf(1020), fact_id: 'f2', holder_id: 'church' });
    store.setHeldBy('f2', null);
    assert.equal(sent.at(-1).holder_id, null);
    assert.ok('holder_id' in sent.at(-1));
    store.handleMessage(reply('set_held_by', { id: 'dr', kind: 'lore', name: 'The Divine Right' }));
    assert.equal(store.thing.name, 'The Divine Right');
    assert.deepEqual(store.pending, {});

    store.pickDate('a', 'b', 'end');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'pick_date', keep_fact_id: 'a', drop_fact_id: 'b', mode: 'end', thing_id: 'dr', at: dateOf(1020) });
    store.handleMessage(reply('pick_date', { keep_fact_id: 'a', drop_fact_id: 'b', mode: 'end', owner_id: 'codex', notes: [], thing: { id: 'dr', kind: 'lore', name: 'After' } }));
    assert.equal(store.thing.name, 'After');
    assert.equal(store.notes, null);
});

check('curation settings: asked for, and only the changes sent', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.getCuration();
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_curation' });
    const knobs = { reach: 1, entries: 12, facts_per_entry: 6, repeat_threshold: 0.4, repeat_untick_threshold: 0.7, timeline_reach: 2 };
    store.handleMessage(reply('get_curation', { settings: knobs, defaults: knobs }));
    assert.deepEqual(store.curation.settings, knobs);
    store.setCuration({ reach: 2 });
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'set_curation', settings: { reach: 2 } });
    assert.equal(store.curationSaved, false);
    store.handleMessage(reply('set_curation', { settings: { ...knobs, reach: 2 }, defaults: knobs }));
    assert.equal(store.curation.settings.reach, 2);
    assert.equal(store.curationSaved, true);
    assert.deepEqual(store.pending, {});
});

check('a being acts in the world only once it is real', () => {
    assert.deepEqual(EXISTENCE, ['real', 'believed', 'undecided']);
    assert.equal(existenceOf({ kind: 'being', fields: {} }), 'undecided');
    assert.equal(existenceOf({ kind: 'being', existence: 'real' }), 'real');
    assert.equal(actsInWorld({ kind: 'being', fields: { existence: 'believed' } }), false);
    assert.equal(actsInWorld({ kind: 'being', existence: 'real' }), true);
    assert.equal(actsInWorld({ kind: 'character' }), true);
    assert.equal(actsInWorld({ kind: 'lore' }), false);
    assert.ok(TOP_KINDS.some((k) => k.kind === 'being'));
    assert.ok(STUB_KINDS.includes('being'));
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
    store.handleMessage(reply('preview_thing', draftOf({ kind: 'mix', prompt: '', fields: {}, name: 'Half-orc', facts: [], prose: {} })));
    store.acceptPreview({ name: 'Half-orc' }, { open: false });
    store.handleMessage(reply('accept_preview', { id: 'm1', kind: 'mix', name: 'Half-orc' }));
    assert.deepEqual(store.accepted, { id: 'm1', kind: 'mix', name: 'Half-orc' });
    assert.equal(store.selectedThingId, null);
    assert.equal(store.previewRequest, null);
    listedEverything(sent.slice(-(ALL_KINDS.length + 1)));
    // the next accept opens its page again
    store.previewThing('character', 'a smith', { heritage: 'm1' });
    store.handleMessage(reply('preview_thing', draftOf({ kind: 'character', prompt: 'a smith', fields: {}, name: 'Gorra', facts: [], prose: {} })));
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
    store.handleMessage(reply('preview_thing', draftOf(preview)));
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

check('events and items are kinds of their own; no sphere kind, and cultures via the skill', () => {
    const top = TOP_KINDS.map((k) => k.kind);
    assert.ok(top.includes('event') && top.includes('item'));
    assert.ok(!top.includes('sphere'));
    // cultures are listed, but made through the culture skill: no listing
    assert.ok(TOP_KINDS.find((k) => k.kind === 'culture').viaSkill);
    assert.ok(!LISTED_KINDS.includes('culture') && !LISTED_KINDS.includes('sphere'));
    assert.ok(!STUB_KINDS.includes('culture') && !STUB_KINDS.includes('race') && !STUB_KINDS.includes('sphere'));
    assert.equal(expandLabel('place'), 'Expand');
    assert.equal(canExpand('place'), true);
    assert.equal(expandNote('place'), null);
});

check('expanding a stub takes its kind as it is', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.expandStub({ id: 'c1', kind: 'lore', name: 'Old Rite' });
    assert.deepEqual(store.expanding, { id: 'c1', kind: 'lore', name: 'Old Rite' });
});

check('a race or mix stub is made from its species page, not expanded', () => {
    // its top-level create box has no species (or parents) to give it
    for (const kind of ['race', 'mix']) {
        assert.equal(canExpand(kind), false, kind);
        assert.equal(expandNote(kind), 'Make it from its species page');
    }
    for (const kind of STUB_KINDS) {
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
    // a kind the store doesn't list (the cultures pointer) isn't asked for
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
    store.handleMessage(reply('preview_thing', draftOf({ kind: 'place', name: 'Tsardom of Moscavia', facts: [], prose: {}, stub_id: 's1' })));
    store.regeneratePreview();
    assert.equal(sent.at(-1).stub_id, 's1');
    // a new version of the same draft
    assert.equal(sent.at(-1).draft_key, 'stub:s1');
    store.handleMessage(reply('preview_thing', draftOf({ kind: 'place', name: 'Tsardom of Moscavia', facts: [], prose: {}, stub_id: 's1' })));
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
    store.handleMessage(reply('preview_thing', draftOf({ kind: 'place', name: 'Kalmara', facts: [], prose: {} })));
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
    store.handleMessage(reply('preview_thing', draftOf({ kind: 'place', name: 'Kalmara', facts: [], prose: {}, matching_stub_id: 'k1' })));

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

check('a fact form needs text, a category and sane years; a timeline fact a year', () => {
    const form = { mode: 'add', text: 'Founded.', category: 'about', fromYear: null, untilYear: null };
    assert.equal(factFormValid(form), true);
    assert.equal(factFormValid({ ...form, text: ' ' }), false);
    assert.equal(factFormValid({ ...form, fromYear: 1010, untilYear: 1005 }), false);
    assert.equal(factFormValid({ ...form, fromYear: '' }), true);
    // a timeline fact is dated: no year, no save (added or corrected)
    assert.equal(factFormValid({ ...form, category: 'timeline' }), false);
    assert.equal(factFormValid({ ...form, category: 'timeline', fromYear: 994 }), true);
    assert.equal(factFormValid({ ...form, mode: 'edit', category: 'timeline', fromYear: '' }), false);
});

// --- the World tab's history (the page's back arrow) -------------------------

const page = (thingId, section = 'species', at = null) => ({ section, thingId, at });
const sectionPage = (section) => ({ section, thingId: null, at: null });

check('a page is its thing (any date), or a section when no thing is open', () => {
    assert.equal(samePage(page('a'), page('a', 'lore', dateOf(900))), true);
    assert.equal(samePage(page('a'), page('b')), false);
    assert.equal(samePage(sectionPage('stubs'), sectionPage('stubs')), true);
    assert.equal(samePage(sectionPage('stubs'), sectionPage('lore')), false);
    assert.equal(samePage(sectionPage('lore'), page('a', 'lore')), false);
    assert.equal(samePage(null, page('a')), false);
});

check('a visit pushes the page left, once; the same page twice pushes nothing', () => {
    let history = historyPushed([], sectionPage('species'), page('a'));
    assert.deepEqual(history, [sectionPage('species')]);
    history = historyPushed(history, page('a'), page('b'));
    assert.deepEqual(history, [sectionPage('species'), page('a')]);
    // opening the open page again (or it as of another date)
    assert.equal(historyPushed(history, page('b'), page('b', 'species', dateOf(900))), history);
    // the page left already on top: not pushed twice
    assert.equal(historyPushed(history, page('a'), page('c')), history);
    // capped, oldest first out
    const long = Array.from({ length: 60 }, (_v, i) => page(`t${i}`));
    const capped = historyPushed(long, page('x'), page('y'), 50);
    assert.equal(capped.length, 50);
    assert.deepEqual(capped.at(-1), page('x'));
});

check('back pops the last page, skipping things that are gone', () => {
    const history = [sectionPage('species'), page('a'), page('gone'), page('b'), page('gone')];
    const gone = (id) => id === 'gone';
    let back = historyBack(history, gone);
    assert.deepEqual(back.page, page('b'));
    assert.deepEqual(back.history, [sectionPage('species'), page('a'), page('gone')]);
    back = historyBack(back.history, gone);
    assert.deepEqual(back.page, page('a'));
    back = historyBack(back.history, gone);
    assert.deepEqual(back.page, sectionPage('species'));
    back = historyBack(back.history, gone);
    assert.deepEqual(back, { page: null, history: [] });
});

check('back from a race opened on its species page returns to the species page', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.showSection('species');
    store.openThing('owlfolk');
    store.openThing('snowy');
    assert.equal(store.selectedThingId, 'snowy');
    store.goBack();
    assert.equal(store.selectedThingId, 'owlfolk');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_thing', id: 'owlfolk', at: null });
    // back again: the Species list
    store.goBack();
    assert.equal(store.selectedThingId, null);
    assert.equal(store.section, 'species');
    // then the Characters list it was opened from; nothing is left after
    store.goBack();
    assert.equal(store.section, 'character');
    assert.deepEqual(store.history, []);
    store.openThing('maren');
    store.goBack();
    store.goBack();
    assert.equal(store.selectedThingId, null);
    assert.equal(store.section, 'character');
});

check('a link chain goes back step by step, as of the date each page was viewed', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('a');
    store.viewThingAt(dateOf(900));
    // a new date on the same page is no visit
    assert.equal(store.history.length, 1);
    store.openThing('b');
    store.openThing('b');
    store.openThing('c');
    assert.equal(store.history.length, 3);
    store.goBack();
    assert.equal(store.selectedThingId, 'b');
    // back doesn't push
    assert.equal(store.history.length, 2);
    store.goBack();
    assert.equal(store.selectedThingId, 'a');
    assert.deepEqual(store.thingAt, dateOf(900));
});

check('back skips a deleted thing, and returns to the Stubs page it came from', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.showSection('stubs');
    store.openThing('maren');
    store.openThing('doomed');
    store.openThing('harbour');
    store.handleMessage(reply('thing_deleted', { id: 'doomed', kind: 'lore' }));
    store.goBack();
    assert.equal(store.selectedThingId, 'maren');
    store.goBack();
    assert.equal(store.selectedThingId, null);
    assert.equal(store.section, 'stubs');
});

check('expanding a stub shows its section, as a visit', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.showSection('stubs');
    store.expandStub({ id: 's1', kind: 'place', name: 'Kremova' });
    assert.equal(store.section, 'place');
    store.goBack();
    assert.equal(store.section, 'stubs');
    store.openThing('lore1');
    store.expandStub({ id: 's2', kind: 'lore', name: 'Vigil' });
    assert.equal(store.section, 'lore');
    store.goBack();
    assert.equal(store.selectedThingId, 'lore1');
});

check('a page back opens that fails to load is skipped: back goes on', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('a');
    store.openThing('b');
    store.openThing('c');
    store.goBack();
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_thing', id: 'b', at: null });
    // b went (deleted elsewhere, say): its get_thing fails
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'no such thing: b' } });
    assert.equal(store.selectedThingId, 'a');
    assert.ok(store.gone.includes('b'));
    // a page that loads clears the watch: a later error goes nowhere
    store.handleMessage(reply('get_thing', { id: 'a', kind: 'lore', name: 'A' }));
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'other' } });
    assert.equal(store.selectedThingId, 'a');
});

check('the history is per world: opening another world starts it afresh', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('a');
    store.openThing('b');
    store.handleMessage(reply('open_world', { ...WORLD, id: 'w2', path: '/worlds/w2' }));
    assert.deepEqual(store.history, []);
    assert.equal(store.section, 'character');
});

check('an accepted preview opens its page as a visit', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.showSection('lore');
    store.previewThing('lore', 'hope');
    store.handleMessage(reply('preview_thing', draftOf({ kind: 'lore', name: 'Hope', facts: [], prose: {} })));
    store.acceptPreview();
    store.handleMessage(reply('accept_preview', { id: 'hope', kind: 'lore', name: 'Hope' }));
    assert.equal(store.selectedThingId, 'hope');
    store.goBack();
    assert.equal(store.selectedThingId, null);
    assert.equal(store.section, 'lore');
});

// --- re-pointing a stub's links ------------------------------------------------

check('repointStub sends the stub and the target; the reply forgets the stub', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.showSection('stubs');
    store.openThing('tsardom');
    store.showSection('stubs');
    store.repointStub('tsardom', 'moscavy');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'repoint_stub', stub_id: 'tsardom', target_id: 'moscavy' });
    assert.equal(store.pending.repoint_stub, true);
    sent.length = 0;
    const target = { id: 'moscavy', kind: 'place', name: 'Moscavy', aka: [] };
    store.handleMessage(reply('repoint_stub', { stub_id: 'tsardom', stub_name: 'Tsardom', target, links: 2, aka_added: ['Tsardom'], facts_moved: 1, notes: ['Moscavy stays in X'] }));
    assert.deepEqual(store.pending, {});
    assert.deepEqual(store.stubRepointed, {
        stubName: 'Tsardom',
        target: { id: 'moscavy', name: 'Moscavy' },
        links: 2,
        akaAdded: ['Tsardom'],
        factsMoved: 1,
        notes: ['Moscavy stays in X'],
    });
    assert.equal(
        repointedNote(store.stubRepointed),
        'Tsardom: 2 links now point to Moscavy, which took 1 fact from it. Moscavy is now also known as Tsardom. Moscavy stays in X.',
    );
    listedEverything(sent);
    // the stub's page is gone from the history; leaving clears the note
    store.openThing('moscavy');
    assert.equal(store.stubRepointed, null);
    store.goBack();
    assert.equal(store.selectedThingId, null);
    assert.equal(store.section, 'stubs');
});

check("re-pointing the open stub's page opens the target's", () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('tsardom');
    store.repointStub('tsardom', 'moscavy');
    const target = { id: 'moscavy', kind: 'place', name: 'Moscavy', aka: [] };
    store.handleMessage(reply('repoint_stub', { stub_id: 'tsardom', stub_name: 'Tsardom', target, links: 1, aka_added: [] }));
    assert.equal(store.selectedThingId, 'moscavy');
    assert.deepEqual(store.thing, target);
    // the stub's page isn't somewhere back goes
    store.goBack();
    assert.equal(store.selectedThingId, null);
});

check('ticking a "Could move here" row unticks the own facts repeating it, and back (ruling C24)', () => {
    const preview = {
        facts: [
            { text: 'The law code, again.', ticked: true, repeat_of: { fact_id: 'm1' } },
            { text: 'Fresh.', ticked: true, repeat_of: null },
            // the owner unticked it themselves: it stays unticked
            { text: 'Another copy.', ticked: false, repeat_of: { fact_id: 'm1' } },
            { text: 'Already in the world.', ticked: false, repeat_of: { fact_id: 'x9' } },
        ],
        move_here: [
            { fact_id: 'm1', text: 'The law code.', ticked: false, picked: true },
            { fact_id: 'm2', text: 'The army.', ticked: false, picked: false },
        ],
    };
    // the owner ticks the pick: its repeat is unticked
    let out = moveInEdit(preview, rowsTicked(preview.move_here, [0], true));
    assert.deepEqual(out.move_here.map((row) => row.ticked), [true, false]);
    assert.deepEqual(out.facts.map((fact) => fact.ticked), [false, true, false, false]);
    // another row ticked: the facts don't change again
    out = moveInEdit({ ...preview, ...out }, rowsTicked(out.move_here, [1], true));
    assert.deepEqual(out.facts.map((fact) => fact.ticked), [false, true, false, false]);
    // the pick unticked: only the fact it unticked comes back
    out = moveInEdit({ ...preview, ...out }, rowsTicked(out.move_here, [0], false));
    assert.deepEqual(out.facts.map((fact) => fact.ticked), [true, true, false, false]);
    assert.equal('untickedByMove' in out.facts[0], false);
    // no facts, no trouble
    assert.deepEqual(moveInEdit({ move_here: [] }, []), { move_here: [], facts: [] });
});

// --- the entry page (Filing, Task 9) -----------------------------------------

check('a tag reads as the backend stores it, its heading pluralised and capitalised', () => {
    assert.equal(normaliseTag('  Royal Seat, old '), 'royal seat');
    assert.equal(normaliseTag(null), '');
    // as filing.tag_heading
    assert.equal(tagHeading('river'), 'Rivers');
    assert.equal(tagHeading('holy site'), 'Holy sites');
    assert.equal(tagHeading('custom'), 'Customs');
    assert.equal(tagHeading('church'), 'Churches');
    assert.equal(tagHeading('box'), 'Boxes');
    assert.equal(tagHeading('city'), 'Cities');
    assert.equal(tagHeading('day'), 'Days');
    assert.equal(tagHeading('species'), 'Specieses');
    assert.equal(tagHeading(null), 'Other');
    assert.equal(tagHeading('  '), 'Other');
});

check("a filing's dates: since, a span once it has ended, until alone", () => {
    assert.equal(filingDates(null, { since: dateOf(979), until: null }), 'since 979');
    assert.equal(filingDates(null, { since: dateOf(900), until: dateOf(1015) }), '900–1015');
    assert.equal(filingDates(null, { since: null, until: dateOf(1015) }), 'until 1015');
    assert.equal(filingDates(null, { since: null, until: null }), '');
    assert.equal(filingDates(null, null), '');
});

check('a group folds its long list: a filter, the first five, then all', () => {
    const rows = Array.from({ length: 8 }, (_v, i) => ({ id: `r${i}`, name: `Custom ${i}`, role: i === 3 ? 'danced here' : null, line_segments: [{ text: i === 6 ? 'A winter dance.' : 'A rite.' }] }));
    assert.equal(GROUP_SHOWN, 5);
    let view = groupView(rows);
    assert.equal(view.long, true);
    assert.deepEqual(view.rows.map((r) => r.id), ['r0', 'r1', 'r2', 'r3', 'r4']);
    assert.equal(view.hidden, 3);
    view = groupView(rows, { showAll: true });
    assert.equal(view.rows.length, 8);
    assert.equal(view.hidden, 0);
    // the filter finds by name, role or line, any case, among all of them
    assert.deepEqual(groupView(rows, { filter: 'WINTER' }).rows.map((r) => r.id), ['r6']);
    assert.deepEqual(groupView(rows, { filter: 'danced' }).rows.map((r) => r.id), ['r3']);
    assert.deepEqual(groupView(rows, { filter: 'custom 7' }).rows.map((r) => r.id), ['r7']);
    assert.equal(groupView(rows, { filter: '  ' }).rows.length, 5);
    // a short group shows every row, and has no filter
    const short = groupView(rows.slice(0, 5), { filter: 'winter' });
    assert.equal(short.long, false);
    assert.equal(short.rows.length, 5);
    assert.equal(short.hidden, 0);
    assert.deepEqual(groupView(null), { long: false, rows: [], hidden: 0 });
});

check('Connected counts its rows; a group is keyed by page and tag', () => {
    assert.equal(connectedCount([{ rows: [1, 2] }, { rows: [3] }]), 3);
    assert.equal(connectedCount(null), 0);
    assert.equal(groupKey('v', 'river'), 'v|river');
    assert.equal(groupKey('v', null), 'v|');
    assert.equal(groupKey('v', undefined), groupKey('v', null));
});

check('a row dropped on another group takes its tag; on its own, nothing', () => {
    assert.equal(dropTag('river', 'district'), 'district');
    assert.equal(dropTag('river', null), null);
    assert.equal(dropTag(null, 'custom'), 'custom');
    assert.equal(dropTag('river', 'river'), undefined);
    assert.equal(dropTag(null, undefined), undefined);
});

check('the tag picker: tags in use holding the query, then a new one', () => {
    const tags = [
        { tag: 'river', heading: 'Rivers', count: 3 },
        { tag: 'lake', heading: 'Lakes', count: 1 },
        { tag: 'place', heading: 'Places', count: 9 },
    ];
    // the entry's own tag is left out
    assert.deepEqual(tagChoices(tags, '', 'river'), { matches: tags.slice(1), fresh: null });
    assert.deepEqual(tagChoices(tags, 'a').matches.map((t) => t.tag), ['lake', 'place']);
    // a new tag, normalised as the backend stores it
    assert.deepEqual(tagChoices(tags, 'Waterway, big'), { matches: [], fresh: 'waterway' });
    // one in use, or its own, is no new tag
    assert.equal(tagChoices(tags, 'Lake').fresh, null);
    assert.equal(tagChoices(tags, 'pond', 'pond').fresh, null);
    assert.deepEqual(tagChoices(null, 'x'), { matches: [], fresh: 'x' });
});

check('"Events ▾": every dated fact, or the event entries\' lines only', () => {
    const lines = [{ fact_id: 'a', owner_id: 'v' }, { fact_id: 'b', owner_id: 'freeze' }, { fact_id: 'c', owner_id: 'court' }];
    assert.equal(timelineShown(lines, 'all', ['freeze']), lines);
    assert.deepEqual(timelineShown(lines, 'events', ['freeze']).map((l) => l.fact_id), ['b']);
    assert.deepEqual(timelineShown(lines, 'events', []), []);
    assert.deepEqual(timelineShown(null, 'events'), []);
});

check('the World tab lists a kind, its stubs last; a place under the first place it is in', () => {
    const things = [
        { id: 'k', name: 'Khorol River', filed_in: ['t', 'v'] },
        { id: 'w', name: 'Wattle Row', stub: { ignored: false }, filed_in: ['v'] },
        { id: 'v', name: 'Velikoye', filed_in: ['t'] },
        { id: 't', name: 'Tsardom of Moscavia', filed_in: [] },
        { id: 'g', name: 'Greensea Strait', filed_in: ['lore-id'] },
    ];
    const flat = kindList(things).map((row) => [row.thing.id, row.depth]);
    assert.deepEqual(flat, [['k', 0], ['v', 0], ['t', 0], ['g', 0], ['w', 0]]);
    const nested = kindList(things, '', { nest: true }).map((row) => [row.thing.id, row.depth]);
    // the river under the Tsardom (its first place), Velikoye too, and
    // the stub Wattle Row under Velikoye; a place in no listed place on top
    assert.deepEqual(nested, [['t', 0], ['k', 1], ['v', 1], ['w', 2], ['g', 0]]);
    // the search keeps what holds it, any case; a place goes under the
    // first of its places still listed, else on top
    assert.deepEqual(kindList(things, 'ROW', { nest: true }).map((row) => [row.thing.id, row.depth]), [['w', 0]]);
    assert.deepEqual(kindList(things, 'e', { nest: true }).map((row) => [row.thing.id, row.depth]), [['v', 0], ['k', 1], ['w', 1], ['g', 0]]);
    // a loop of places never hangs: each sits on top
    const loop = [{ id: 'a', name: 'A', filed_in: ['b'] }, { id: 'b', name: 'B', filed_in: ['a'] }];
    assert.deepEqual(kindList(loop, '', { nest: true }).map((row) => [row.thing.id, row.depth]), [['a', 0], ['b', 0]]);
    assert.deepEqual(kindList(undefined), []);
});

check('the page lists its facts without its summary or a person\'s "but…"s', () => {
    const thing = {
        facts: [{ fact_id: 's', summary: true }, { fact_id: 'f' }, { fact_id: 'b' }],
        in: [{ target_id: 't', exceptions: [{ fact_id: 'b' }] }],
    };
    assert.deepEqual(listedFacts(thing).map((f) => f.fact_id), ['f']);
    assert.deepEqual(listedFacts(null), []);
});

check('filing edits go out for the open page, at its date; only what changes', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('dmitry', dateOf(1000));
    store.addFiling({ targetId: 'court', role: 'presides', since: { ...dateOf(995), label: '995' } });
    assert.deepEqual(sent.at(-1), {
        type: 'worlds',
        action: 'add_filing',
        thing_id: 'dmitry',
        at: dateOf(1000),
        target_id: 'court',
        role: 'presides',
        since: dateOf(995),
        until: null,
        within: null,
    });
    assert.equal(store.pending.add_filing, true);
    // a new stub: its name, kind and tag, no target
    store.addFiling({ newName: 'The Frost Council', kind: 'lore', tag: 'council' });
    const made = sent.at(-1);
    assert.equal('target_id' in made, false);
    assert.deepEqual([made.new_name, made.kind, made.tag, made.role], ['The Frost Council', 'lore', 'council', null]);
    // only the keys that change; "End this" is an until
    store.editFiling('court', { until: dateOf(1010) });
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'edit_filing', thing_id: 'dmitry', at: dateOf(1000), target_id: 'court', until: dateOf(1010) });
    store.editFiling('court', { role: null });
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'edit_filing', thing_id: 'dmitry', at: dateOf(1000), target_id: 'court', role: null });
    store.removeFiling('court');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'remove_filing', thing_id: 'dmitry', at: dateOf(1000), target_id: 'court' });
    store.addException('tsardom', 'Rules only in winter.');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'add_exception', character_id: 'dmitry', target_id: 'tsardom', text: 'Rules only in winter.', rejects: null, at: dateOf(1000) });
    // another entry's tag (a dragged row): at the latest, not the page's date
    store.setTag('river', 'district');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'set_tag', thing_id: 'river', at: null, tag: 'district' });
});

check("a filing edit's reply: the open page takes it, another thing's refreshes it", () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('velikoye');
    store.handleMessage(reply('get_thing', { id: 'velikoye', kind: 'place', name: 'Velikoye' }));
    sent.length = 0;
    // a Connected row retagged: its own page answers, so the open one is asked for
    store.setTag('river', 'district');
    sent.length = 0;
    store.handleMessage(reply('set_tag', { id: 'river', kind: 'place', name: 'Khorol River' }));
    assert.equal(store.thing.id, 'velikoye');
    assert.deepEqual(sent[0], { type: 'worlds', action: 'get_thing', id: 'velikoye', at: null });
    assert.ok(sent.some((m) => m.action === 'list_tags'));
    listedEverything(sent);
    assert.deepEqual(store.pending, {});
    // the open page's own: taken as it is, its notes shown
    store.handleMessage(reply('remove_filing', { id: 'velikoye', kind: 'place', name: 'Velikoye', in: [], notes: ['Removed the "but..."'] }));
    assert.deepEqual(store.thing.in, []);
    assert.deepEqual(store.notes, { action: 'remove_filing', notes: ['Removed the "but..."'] });
});

check('tags: listed on opening a world, renamed and merged', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    assert.ok(sent.some((m) => m.action === 'list_tags'));
    const tags = [{ tag: 'school', heading: 'Schools', count: 1 }, { tag: 'institution', heading: 'Institutions', count: 2 }];
    store.handleMessage(reply('list_tags', { tags }));
    assert.deepEqual(store.tags, tags);
    store.openThing('velikoye');
    store.renameTag('school', 'academy');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'rename_tag', old: 'school', new: 'academy' });
    sent.length = 0;
    const renamed = [{ tag: 'academy', heading: 'Academies', count: 1 }, tags[1]];
    store.handleMessage(reply('rename_tag', { old: 'school', new: 'academy', changed: ['a'], tags: renamed }));
    assert.deepEqual(store.tags, renamed);
    // the Tags tab closes the form this answers, not on a mere listing
    assert.deepEqual(store.tagsChanged, { from: 'school', to: 'academy' });
    store.handleMessage(reply('list_tags', { tags: renamed }));
    assert.deepEqual(store.tagsChanged, { from: 'school', to: 'academy' });
    // the open page reads its new groups
    assert.deepEqual(sent[0], { type: 'worlds', action: 'get_thing', id: 'velikoye', at: null });
    store.mergeTag('academy', 'institution');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'merge_tag', from: 'academy', into: 'institution' });
    store.handleMessage(reply('merge_tag', { from: 'academy', into: 'institution', changed: ['a'], tags: [tags[1]] }));
    assert.deepEqual(store.tagsChanged, { from: 'academy', to: 'institution' });
    assert.deepEqual(store.tags, [tags[1]]);
    assert.deepEqual(store.pending, {});
});

check("a group's synopsis: asked for, kept by page and tag, forced again", () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.groupSynopsis('v', 'custom');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'group_synopsis', thing_id: 'v', tag: 'custom', force: false });
    assert.equal(store.synopses['v|custom'].pending, true);
    // another group's reply leaves it waiting
    store.handleMessage(reply('group_synopsis', { thing_id: 'v', tag: 'river', synopsis: 'Rivers.' }));
    assert.equal(store.synopses['v|river'], undefined);
    store.handleMessage(reply('group_synopsis', { thing_id: 'v', tag: 'custom', synopsis: 'Customs.' }));
    assert.deepEqual(store.synopses['v|custom'], { pending: false, text: 'Customs.', error: null });
    store.groupSynopsis('v', 'custom', true);
    assert.equal(sent.at(-1).force, true);
    // a failure keeps the text it had, says why
    store.handleMessage({ type: 'worlds', action: 'group_synopsis_failed', message: 'no reply', data: { thing_id: 'v', tag: 'custom' } });
    assert.deepEqual(store.synopses['v|custom'], { pending: false, text: 'Customs.', error: 'no reply' });
    // the untagged group goes as null
    store.groupSynopsis('v', null);
    assert.equal(sent.at(-1).tag, null);
    // an error stops it waiting
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'no AI client' } });
    assert.equal(store.synopses['v|'].pending, false);
});

check('a group\'s "+ Add": drafted rows, edited, the ticked ones accepted', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('v');
    store.groupAdd('v', 'institution', 'two guilds');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'group_add', thing_id: 'v', tag: 'institution', prompt: 'two guilds' });
    const rows = [
        { name: 'The Icewrights', kind: 'lore', tag: 'institution', line: 'Pilots.', ticked: true },
        { name: 'The Owl Post', kind: 'lore', tag: 'institution', line: 'Letters.', ticked: true },
    ];
    store.handleMessage(reply('group_add', { thing_id: 'v', tag: 'institution', rows }));
    assert.deepEqual(store.groupAdds['v|institution'].rows, rows);
    store.editGroupAdd('v', 'institution', [{ ...rows[0], name: 'The Ice Guild' }, { ...rows[1], ticked: false }]);
    store.acceptGroupAdd('v', 'institution');
    const accept = {
        type: 'worlds',
        action: 'accept_group_add',
        thing_id: 'v',
        rows: [{ ...rows[0], name: 'The Ice Guild' }, { ...rows[1], ticked: false }],
    };
    assert.deepEqual(sent.at(-1), accept);
    // kept until the server answers: a failure leaves the rows as they were
    assert.equal(store.groupAdds['v|institution'].accepting, true);
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'refused' } });
    assert.equal(store.groupAdds['v|institution'].accepting, false);
    assert.equal(store.groupAdds['v|institution'].rows[0].name, 'The Ice Guild');
    store.acceptGroupAdd('v', 'institution');
    assert.deepEqual(sent.at(-1), accept);
    store.handleMessage(reply('accept_group_add', { id: 'v', kind: 'place', name: 'Velikoye', thing_ids: ['g'], notes: [] }));
    assert.equal(store.groupAdds['v|institution'], undefined);
    assert.equal(store.thing.id, 'v');
    assert.equal(store.notes, null);
    // the page's own "+ Add" (no tag), failed: the error shows, then it's discarded
    store.groupAdd('v', null, 'a landmark');
    assert.equal(sent.at(-1).tag, null);
    store.handleMessage({ type: 'worlds', action: 'group_add_failed', message: 'unusable', data: { thing_id: 'v', tag: null } });
    assert.deepEqual(store.groupAdds['v|'], { prompt: 'a landmark', pending: false, rows: null, error: 'unusable' });
    store.discardGroupAdd('v', null);
    assert.deepEqual(store.groupAdds, {});
});

check('"+ Add facts…" and "+ Add event…": a draft to tick, then written', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('v', dateOf(1000));
    store.addFacts('its laws');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'add_facts', thing_id: 'v', at: dateOf(1000), prompt: 'its laws' });
    assert.equal(store.factDraft.mode, 'facts');
    const draft = { thing_id: 'v', prompt: 'its laws', year: null, facts: [{ category: 'law', text: 'No flying.', ticked: true }, { category: 'general', text: 'Bells.', ticked: true }] };
    const facts = [{ index: 0, rendered: 'No flying.', ticked: true }, { index: 1, rendered: 'Bells.', ticked: true }];
    // a draft page's own addition (Task 10) is not this one
    store.handleMessage(reply('add_facts', { draft_key: 'new:lore:x', facts: [] }));
    assert.equal(store.factDraft.pending, true);
    store.handleMessage(reply('add_facts', { thing_id: 'v', draft, facts }));
    assert.equal(store.factDraft.pending, false);
    store.tickDraftFact(1, false);
    assert.deepEqual(store.factDraft.facts.map((f) => f.ticked), [true, false]);
    store.acceptFacts();
    assert.equal(sent.at(-1).action, 'accept_facts');
    assert.deepEqual(sent.at(-1).draft.facts.map((f) => f.ticked), [true, false]);
    assert.deepEqual(sent.at(-1).at, dateOf(1000));
    // kept until the server answers: a failure leaves the ticks as they were
    assert.equal(store.factDraft.accepting, true);
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'refused' } });
    assert.equal(store.factDraft.accepting, false);
    assert.deepEqual(store.factDraft.facts.map((f) => f.ticked), [true, false]);
    store.acceptFacts();
    store.handleMessage(reply('accept_facts', { id: 'v', kind: 'place', name: 'Velikoye', fact_ids: ['f'] }));
    assert.equal(store.factDraft, null);
    // an event: its year goes along; a failure says why
    store.addEvent('the bluff collapse', 1012);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'add_event', thing_id: 'v', at: dateOf(1000), prompt: 'the bluff collapse', year: 1012 });
    store.handleMessage({ type: 'worlds', action: 'add_event_failed', message: 'no facts', data: { thing_id: 'v' } });
    assert.equal(store.factDraft.error, 'no facts');
    store.discardFacts();
    assert.equal(store.factDraft, null);
});

check("a page's synopsis: the server's wins; the session's goes on a refetch", () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('v');
    store.groupSynopsis('v', 'custom');
    store.handleMessage(reply('group_synopsis', { thing_id: 'v', tag: 'custom', synopsis: 'Customs.' }));
    assert.equal(store.synopses['v|custom'].text, 'Customs.');
    // the page fetched again (a member changed): its own synopsis stands,
    // null when the cached one went stale
    store.handleMessage(reply('get_thing', { id: 'v', kind: 'place', name: 'Velikoye', connected: [{ tag: 'custom', synopsis: null, rows: [] }] }));
    assert.equal(store.synopses['v|custom'], undefined);
    // one still being asked for is kept
    store.groupSynopsis('v', 'river');
    store.handleMessage(reply('get_thing', { id: 'v', kind: 'place', name: 'Velikoye', connected: [] }));
    assert.equal(store.synopses['v|river'].pending, true);
    // another page's are left alone
    store.groupSynopsis('k', 'custom');
    store.handleMessage(reply('group_synopsis', { thing_id: 'k', tag: 'custom', synopsis: 'K.' }));
    store.handleMessage(reply('get_thing', { id: 'v', kind: 'place', name: 'Velikoye', connected: [] }));
    assert.equal(store.synopses['k|custom'].text, 'K.');
});

// --- the draft page (Filing, Task 10) ------------------------------------------

const HOST = {
    kind: 'lore', prompt: 'a host', fields: {}, name: 'The Frostwing Host', prose: {}, aka: [],
    facts: [
        { category: 'general', text: 'It flies at night.', ticked: true },
        { category: 'general', text: 'The Khorol freezes.', ticked: false, repeat_of: { fact_id: 'f9', owner_id: 'vel', owner_name: 'Velikoye', text: 'The Khorol freezes solid.' } },
    ],
    filings: [{ target_id: 'ts', target_name: 'Tsardom', role: "the realm's army", ticked: false, exceptions: [] }],
    file_into: [{ thing_id: 'wt', name: 'White Talon', ticked: false }],
    move_here: [{ fact_id: 'm1', from_id: 'vel', from_name: 'Velikoye', text: 'The Host drills here.', ticked: false }],
    new_names: [{ name: 'Pale Wing', kind: 'lore', tag: null }],
    elsewhere: [{ target_id: 'vel', target_name: 'Velikoye', new: null, category: 'description', text: 'Velikoye closes its bridges.', ticked: true }],
    picks: {},
};

function hostDraft() {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.previewThing('lore', 'a host');
    store.handleMessage(reply('preview_thing', draftOf(HOST)));
    return { store, sent };
}

check("the owner's draft edits are rebased onto the server's next copy", () => {
    const base = HOST;
    let edited = { ...base, name: 'The Frostwing Riders' };
    edited = { ...edited, ...tickFact(edited, 0, false) };
    edited = { ...edited, ...changeFiling(edited, 'ts', { ticked: true }) };
    edited = { ...edited, ...addFiling(edited, { id: 'nc', name: 'The Night Court' }) };
    edited = { ...edited, ...alsoHere(edited, base.elsewhere[0]) };
    edited = { ...edited, ...changeNewName(edited, 'Pale Wing', { kind: 'place' }) };
    // the server's copy since: a fact appended, a new name said anew
    const next = {
        ...base,
        facts: [...base.facts, { category: 'general', text: 'It drills at dawn.', ticked: true }],
        new_names: [{ name: 'Pale Wing', kind: 'item', tag: 'banner' }, { name: 'Frost Field', kind: 'place' }],
    };
    const out = rebaseDraft(base, edited, next);
    assert.equal(out.name, 'The Frostwing Riders');
    // the server's facts in place, the owner's ticks on them, its own after
    assert.deepEqual(out.facts.map((f) => [f.text, f.ticked, !!f.local]), [
        ['It flies at night.', false, false],
        ['The Khorol freezes.', false, false],
        ['It drills at dawn.', true, false],
        ['Velikoye closes its bridges.', true, true],
    ]);
    assert.deepEqual(out.filings.map((f) => [f.target_id, f.ticked]), [['ts', true], ['nc', true]]);
    // the owner's change kept on a row the server still has, unless the
    // server has just said it anew (`fresh`)
    assert.deepEqual(out.new_names.map((n) => [n.name, n.kind]), [['Pale Wing', 'place'], ['Frost Field', 'place']]);
    const fresh = rebaseDraft(base, edited, next, { fresh: ['pale wing'] });
    assert.deepEqual(fresh.new_names[0], { name: 'Pale Wing', kind: 'item', tag: 'banner' });
    // nothing to rebase from: the server's copy as it is
    assert.equal(rebaseDraft(null, null, next), next);
});

check("a draft fact removed or moved keeps its place, so the server's indices hold", () => {
    let edited = { ...HOST };
    edited = { ...edited, ...moveFactTo(edited, 0, { id: 'nc', name: 'The Night Court', kind: 'lore' }) };
    assert.deepEqual(edited.facts.map((f) => [f.ticked, !!f.removed]), [[false, true], [false, false]]);
    assert.deepEqual(edited.elsewhere.at(-1), {
        target_id: 'nc', target_name: 'The Night Court', new: null, category: 'general', text: 'It flies at night.',
        since: null, held_by: null, held_by_name: null, ticked: true, repeat_of: null, local: true,
    });
    // a copy keeps it here; a place's categories are the place's
    const copied = copyFactTo(HOST, 0, { id: 'vel', name: 'Velikoye', kind: 'place' });
    assert.equal(copied.elsewhere.at(-1).category, 'general');
    assert.equal(categoryFor('place', 'general'), 'general');
    assert.equal(categoryFor('place', 'nature'), 'general');
    assert.equal(categoryFor('character', 'nature'), 'appearance');
    assert.equal(categoryFor('lore', 'general'), 'general');
    // the page's rows: the removed one left out, each with the server's index
    const page = draftOf(HOST);
    const rows = draftFactRows(page, edited);
    assert.deepEqual(rows.map((r) => [r.index, r.serverIndex, r.edited]), [[1, 1, false]]);
    // removed and held
    assert.equal(removeFact(HOST, 1).facts[1].removed, true);
    assert.deepEqual(holdFact(HOST, 0, { id: 'ch', name: 'Church' }).facts[0].held_by_name, 'Church');
    assert.equal(holdFact(HOST, 0, null).facts[0].held_by, null);
});

check('a draft fact rewritten here, or added, has no server index: its words show plain, new names fresh', () => {
    const page = draftOf(HOST);
    let edited = { ...HOST, facts: HOST.facts.map((f, i) => (i === 0 ? { ...f, text: 'It flies with the Pale Wing.' } : f)) };
    edited = { ...edited, ...alsoHere(edited, edited.elsewhere[0]) };
    const rows = draftFactRows(page, edited);
    assert.deepEqual(rows.map((r) => [r.serverIndex, r.edited, r.local]), [[null, true, false], [1, false, false], [null, true, true]]);
    assert.deepEqual(rows[0].segments.map((seg) => [seg.text, !!seg.fresh]), [['It flies with the ', false], ['Pale Wing', true], ['.', false]]);
    // a linked run stays linked; a name answered "same as" isn't fresh
    assert.deepEqual(freshSegments([{ text: 'Pale Wing', ref: 'x', stub: false }], HOST.new_names), [{ text: 'Pale Wing', ref: 'x', stub: false }]);
    assert.equal(freshSegments([{ text: 'Pale Wing', ref: null, stub: false }], [{ name: 'Pale Wing', same_target_id: 'pw' }])[0].fresh, undefined);
});

check('a repeat: Move that one here, Keep both or Drop this', () => {
    let edited = { ...HOST, ...settleRepeat(HOST, 1, 'move') };
    assert.deepEqual([edited.facts[1].ticked, edited.facts[1].moveRepeat], [false, true]);
    assert.deepEqual(edited.move_here.at(-1), {
        fact_id: 'f9', from_id: 'vel', from_name: 'Velikoye', text: 'The Khorol freezes solid.', ticked: true, repeat: true, local: true,
    });
    assert.equal(previewCounts(edited).movedIn, 1);
    edited = { ...edited, ...settleRepeat(edited, 1, 'keep') };
    assert.deepEqual([edited.facts[1].ticked, edited.facts[1].moveRepeat], [true, false]);
    assert.equal(edited.move_here.filter((row) => row.repeat).length, 0);
    edited = { ...edited, ...settleRepeat(edited, 1, 'drop') };
    assert.equal(edited.facts[1].ticked, false);
    // a Could move here tick leaves a repeat row alone
    const moving = { ...HOST, ...settleRepeat(HOST, 1, 'move') };
    assert.deepEqual(tickMoveHere(moving, 'f9', false).move_here.map((r) => r.ticked), [false, true]);
    assert.deepEqual(tickMoveHere(moving, 'm1', true).move_here.map((r) => r.ticked), [true, true]);
});

check('For other pages: a row retargeted, "+ also here"; In, File into this and new names', () => {
    const out = retarget(HOST, 0, { id: 'nc', name: 'The Night Court', kind: 'lore' });
    assert.deepEqual(out.elsewhere[0], {
        target_id: 'nc', target_name: 'The Night Court', new: null, category: 'general', text: 'Velikoye closes its bridges.', ticked: true, repeat_of: null,
    });
    const also = alsoHere(HOST, HOST.elsewhere[0]);
    assert.deepEqual(also.facts.at(-1), {
        category: 'general', text: 'Velikoye closes its bridges.', since: null, overrides: [], held_by: null, held_by_name: null, ticked: true, repeat_of: null, local: true,
    });
    // "+ in…" a filing already there ticks it
    assert.deepEqual(addFiling(HOST, { id: 'ts', name: 'Tsardom' }).filings.map((f) => f.ticked), [true]);
    assert.deepEqual(tickFileInto(HOST, 'wt', true).file_into[0].ticked, true);
    assert.equal(changeNewName(HOST, 'the Pale Wing', { tag: 'banner' }).new_names[0].tag, 'banner');
    // the draft's own names highlighted in a Could move here row
    const segments = namedSegments('The Host drills by the Frostwing Host.', { name: 'The Frostwing Host', aka: [{ name: 'the Host' }], kind: 'lore' });
    assert.deepEqual(segments.filter((seg) => seg.fresh).map((seg) => seg.text), ['The Host', 'the Frostwing Host']);
    assert.deepEqual(namedSegments('Nothing here.', { name: 'Host' }), [{ text: 'Nothing here.', ref: null, stub: false }]);
    // what's accepted leaves the page's own keys out
    assert.deepEqual(acceptable({ name: 'x', _same: 'a' }), { name: 'x' });
    assert.deepEqual(versionRows([{ version: 1, name: 'A', prompt: 'p' }, { version: 2, name: 'B', prompt: 'q' }], 1).map((r) => [r.label, r.current]), [['v2 · B', false], ['v1 · A', true]]);
});

check("versions: the owner's edits kept per version for the session, restored with it", () => {
    const { store, sent } = hostDraft();
    assert.equal(store.draft.key, 'new:lore:frostwing host');
    store.editDraft(tickFact(store.preview, 0, false));
    // Regenerate: the draft's key goes back, a second version comes
    store.regeneratePreview();
    assert.equal(sent.at(-1).draft_key, 'new:lore:frostwing host');
    store.handleMessage(reply('preview_thing', draftOf({ ...HOST, facts: [{ category: 'general', text: 'It hunts.' }] }, { version: 2 })));
    assert.deepEqual(store.preview.facts.map((f) => f.text), ['It hunts.']);
    // version 1 again: the server's copy, the owner's untick on it
    store.useVersion(1);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'use_version', draft_key: 'new:lore:frostwing host', version: 1 });
    store.handleMessage(reply('use_version', draftOf(HOST, { version: 1, count: 2 })));
    assert.equal(store.draft.version, 1);
    assert.equal(store.preview.facts[0].ticked, false);
    // a reply nobody asked for is dropped
    store.handleMessage(reply('preview_thing', draftOf(HOST, { version: 3, count: 3 })));
    assert.equal(store.draft.version, 1);
    assert.deepEqual(Object.keys(store.draftEdits['new:lore:frostwing host']), ['1', '2']);
    // the oldest version dropped (five kept): the edits kept move down
    store.draft = { ...store.draft, versions: [1, 2, 3, 4, 5].map((n) => ({ version: n })), version: 5 };
    store.regeneratePreview();
    store.handleMessage(reply('preview_thing', draftOf(HOST, { version: 5, count: 5 })));
    assert.deepEqual(Object.keys(store.draftEdits['new:lore:frostwing host']), ['1', '4']);
    // Edit prompt: back to the box, the draft kept; Discard: every version goes
    store.editPrompt();
    assert.equal(store.draftShown, false);
    store.previewThing('lore', 'a host, again');
    assert.equal(sent.at(-1).draft_key, 'new:lore:frostwing host');
    store.handleMessage(reply('preview_thing', draftOf(HOST, { version: 5, count: 5 })));
    assert.equal(store.draftShown, true);
    store.discardPreview();
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'discard_preview', draft_key: 'new:lore:frostwing host' });
    assert.equal(store.draft, null);
    assert.equal(store.draftEdits['new:lore:frostwing host'], undefined);
    // another kind's draft drops this one, once the owner agrees
    const other = hostDraft();
    other.store.previewThing('place', 'a town');
    other.store.confirmCreate();
    assert.equal(other.sent.at(-2).action, 'discard_preview');
    assert.equal('draft_key' in other.sent.at(-1), false);
});

check("a draft's additions: one at a time, rebased; a stale one is said", () => {
    const { store, sent } = hostDraft();
    store.editDraft(tickFact(store.preview, 0, false));
    store.addDraftFacts('its drills');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'add_facts', draft_key: 'new:lore:frostwing host', prompt: 'its drills' });
    assert.equal(store.draft.adding, 'add_facts');
    // a second waits for the first
    sent.length = 0;
    store.addDraftFacts('more', 990);
    assert.deepEqual(sent, []);
    // another draft's reply is dropped; this one's is rebased
    store.handleMessage(reply('add_facts', draftOf(HOST, { key: 'new:lore:other' })));
    assert.equal(store.draft.adding, 'add_facts');
    const added = { ...HOST, facts: [...HOST.facts, { category: 'general', text: 'It drills.', ticked: true }] };
    store.handleMessage(reply('add_facts', draftOf(added)));
    assert.equal(store.draft.adding, null);
    assert.deepEqual(store.preview.facts.map((f) => f.ticked), [false, false, true]);
    // an event, refused as stale (another version current meanwhile)
    store.addDraftFacts('its raising', 990);
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'add_event', draft_key: 'new:lore:frostwing host', prompt: 'its raising', year: 990 });
    store.handleMessage({ type: 'worlds', action: 'add_event_failed', message: 'ask again', data: { draft_key: 'new:lore:frostwing host', stale: true } });
    assert.equal(store.draft.adding, null);
    assert.equal(store.draft.addError, 'ask again');
    // the entry page's own fact draft is left alone by a draft's reply
    assert.equal(store.factDraft, null);
});

check('selected words: on a draft a stub or a link by its index; on a page by the fact', () => {
    const { store, sent } = hostDraft();
    store.draftSelection('make_stub_from_text', 0, 9, 18, { kind: 'lore', tag: 'banner' });
    assert.deepEqual(sent.at(-1), {
        type: 'worlds', action: 'make_stub_from_text', draft_key: 'new:lore:frostwing host', index: 0, start: 9, end: 18, kind: 'lore', tag: 'banner',
    });
    assert.equal(store.draft.selecting, 'make_stub_from_text');
    store.editDraft(changeNewName(store.preview, 'Pale Wing', { kind: 'place' }));
    const named = { ...HOST, new_names: [{ name: 'Pale Wing', kind: 'lore', tag: 'banner' }] };
    store.handleMessage(reply('make_stub_from_text', { ...draftOf(named), stub_id: null, new_name: 'Pale Wing' }));
    assert.equal(store.draft.selecting, null);
    // the words said anew: the server's row as it is
    assert.deepEqual(store.preview.new_names, [{ name: 'Pale Wing', kind: 'lore', tag: 'banner' }]);
    store.draftSelection('link_text', 0, 0, 2, { target_id: 'vel' });
    store.handleMessage(reply('link_text', draftOf({ ...named, picks: { It: 'vel' } })));
    assert.deepEqual(store.preview.picks, { It: 'vel' });

    // on an accepted page: the fact's id, then the page; "expand now"
    // opens the new stub's box
    const page = freshStore();
    page.store.handleMessage(reply('open_world', WORLD));
    page.store.openThing('vel');
    page.store.makeStubFromText('f1', 7, 17, 'place', 'gate', { expand: true, words: 'Ashen Gate' });
    assert.deepEqual(page.sent.at(-1), {
        type: 'worlds', action: 'make_stub_from_text', thing_id: 'vel', at: null, fact_id: 'f1', start: 7, end: 17, kind: 'place', tag: 'gate',
    });
    page.store.handleMessage(reply('make_stub_from_text', { id: 'vel', kind: 'place', name: 'Velikoye', stub_id: 'g1' }));
    assert.deepEqual(page.store.expanding, { id: 'g1', kind: 'place', name: 'Ashen Gate' });
    page.store.openThing('vel');
    page.store.linkText('f1', 29, 39, 'ts');
    assert.deepEqual(page.sent.at(-1), { type: 'worlds', action: 'link_text', thing_id: 'vel', at: null, fact_id: 'f1', start: 29, end: 39, target_id: 'ts' });
    page.store.handleMessage(reply('link_text', { id: 'vel', kind: 'place', name: 'Velikoye', facts: [] }));
    assert.equal(page.store.thing.name, 'Velikoye');
});

check('Copy to… keeps the fact; the hard re-point sends the name; names fetched for it', () => {
    const { store, sent } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.openThing('vel');
    store.copyFact('f1', 'ts');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'copy_fact', fact_id: 'f1', target_id: 'ts' });
    store.handleMessage(reply('copy_fact', { fact_id: 'f2', target: { id: 'ts', name: 'Tsardom' }, notes: [] }));
    assert.deepEqual(store.notes, { action: 'copy_fact', notes: ['Copied to Tsardom'] });
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'get_thing', id: 'vel', at: null });
    store.fetchNames('ts');
    store.handleMessage(reply('get_thing', { id: 'ts', name: 'Tsardom', aka: [{ name: 'the realm' }] }));
    assert.deepEqual(store.namesOf.ts, ['Tsardom', 'the realm']);
    store.repointStub('s1', 'ts', 'the realm');
    assert.deepEqual(sent.at(-1), { type: 'worlds', action: 'repoint_stub', stub_id: 's1', target_id: 'ts', use_name: 'the realm' });
    store.repointStub('s1', 'ts');
    assert.equal('use_name' in sent.at(-1), false);
});

// --- Task 10 fix round 1 -------------------------------------------------------

check('a draft\'s "+ in…" can make a stub of a typed name; removing an In row', () => {
    const out = addFiling(HOST, { newName: 'The Owl Legion', kind: 'lore', tag: 'army' }, { role: 'a wing of' });
    const row = out.filings.at(-1);
    assert.deepEqual(row, {
        target_id: null, new_name: { name: 'The Owl Legion', kind: 'lore', tag: 'army' }, target_name: 'The Owl Legion',
        role: 'a wing of', since: null, within: null, exceptions: [], ticked: true, local: true,
    });
    assert.equal(filingKey(row), 'new:owl legion');
    assert.equal(filingKey(HOST.filings[0]), 'ts');
    // the owner's own goes; the AI's is unticked
    let edited = { ...HOST, ...out };
    edited = { ...edited, ...removeFiling(edited, 'new:owl legion') };
    assert.deepEqual(edited.filings.map((f) => f.target_id), ['ts']);
    edited = { ...edited, ...removeFiling(edited, 'ts') };
    assert.deepEqual(edited.filings.map((f) => f.ticked), [false]);
    // rebased by its key
    const rebased = rebaseDraft(HOST, { ...HOST, ...out }, HOST);
    assert.equal(rebased.filings.at(-1).target_name, 'The Owl Legion');
});

check("a draft's kind changed: its facts' categories follow, other pages' don't", () => {
    const out = changeKind(HOST, 'character');
    assert.equal(out.kind, 'character');
    assert.deepEqual(out.facts.map((f) => f.category), ['appearance', 'appearance']);
    assert.equal('elsewhere' in out, false);
});

check("the owner's selections are highlighted in any case (ruling F26)", () => {
    const names = [{ name: 'bells', kind: 'item' }];
    const plain = [{ text: 'The Bells ring; bells sound.', ref: null, stub: false }];
    assert.deepEqual(freshSegments(plain, names).filter((seg) => seg.fresh).map((seg) => seg.text), ['bells']);
    assert.deepEqual(freshSegments(plain, names, ['bells']).filter((seg) => seg.fresh).map((seg) => seg.text), ['Bells', 'bells']);
});

check('creating in another box while a draft is open asks first', () => {
    const { store, sent } = hostDraft();
    sent.length = 0;
    store.previewThing('place', 'a ford');
    assert.deepEqual(sent, []);
    assert.equal(store.createAsk.kind, 'place');
    assert.equal(store.previewPending, false);
    store.keepPreview();
    assert.equal(store.createAsk, null);
    assert.equal(store.draft.key, 'new:lore:frostwing host');
    store.previewThing('place', 'a ford');
    store.confirmCreate();
    assert.deepEqual(sent.map((m) => m.action), ['discard_preview', 'preview_thing']);
    assert.equal(sent.at(-1).kind, 'place');
    assert.equal('draft_key' in sent.at(-1), false);
    assert.equal(store.createAsk, null);
    // a draft whose kind the owner changed regenerates as the same draft
    const other = hostDraft();
    other.store.editDraft(changeKind(other.store.preview, 'character'));
    other.store.regeneratePreview();
    assert.equal(other.sent.at(-1).draft_key, 'new:lore:frostwing host');
    assert.equal(other.store.createAsk, null);
});

check('names asked for and failed stop waiting', () => {
    const { store } = freshStore();
    store.handleMessage(reply('open_world', WORLD));
    store.fetchNames('gone');
    assert.deepEqual(store.namesWanted, ['gone']);
    store.handleMessage({ type: 'worlds', action: 'operation_done', error: { message: 'no such thing' } });
    assert.deepEqual(store.namesWanted, []);
    assert.equal(store.namesFailed, 'gone');
});

if (failures.length) {
    for (const { name, err } of failures) {
        console.error(`FAIL ${name}\n  ${err.message}`);
    }
    console.error(`${failures.length} failed, ${passed} passed`);
    process.exit(1);
}
console.log(`ok ${passed} worlds checks passed`);
